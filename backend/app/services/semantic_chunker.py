import hashlib
from typing import List, Optional

from app.schemas.ast_nodes import CodeSymbolType, ParsedCodeSymbol
from app.schemas.chunk import ChunkingSummary, CodeChunk
from app.services.ast_parser import ast_parser_service


class SemanticChunkerService:
    """Semantic code chunker preserving function/class boundaries and line ranges."""

    # Target chunk token limits
    MAX_CHUNK_TOKENS: int = 800
    MIN_CHUNK_TOKENS: int = 40

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count for code content (1 token ~ 3.5 characters)."""
        if not text:
            return 0
        return max(1, int(len(text) / 3.5))

    @staticmethod
    def generate_chunk_id(repo_id: str, file_path: str, start_line: int, end_line: int) -> str:
        """Generate deterministic 16-char hex identifier for the chunk."""
        raw = f"{repo_id}:{file_path}:{start_line}:{end_line}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _format_chunk_content(
        self, file_path: str, symbol: ParsedCodeSymbol, language: str
    ) -> str:
        """Prepend metadata breadcrumb comment so LLM retains structural context during retrieval."""
        comment_prefix = "#" if language in ("python", "ruby", "shell") else "//"
        scope_info = f" | Scope: {symbol.name}" if symbol.name else ""
        header = f"{comment_prefix} File: {file_path}{scope_info} (Lines {symbol.start_line}-{symbol.end_line})\n"
        return header + symbol.body_text

    def chunk_file(
        self, repo_id: str, file_path: str, source_code: str
    ) -> List[CodeChunk]:
        """Convert a source code file into semantically intact code chunks."""
        ast_result = ast_parser_service.parse_file(file_path, source_code)
        chunks: List[CodeChunk] = []

        for symbol in ast_result.symbols:
            content = self._format_chunk_content(file_path, symbol, ast_result.language)
            token_count = self.estimate_tokens(content)

            # If symbol fits in target token budget, save as a single intact chunk
            if token_count <= self.MAX_CHUNK_TOKENS:
                chunk_id = self.generate_chunk_id(
                    repo_id, file_path, symbol.start_line, symbol.end_line
                )
                chunks.append(
                    CodeChunk(
                        chunk_id=chunk_id,
                        repo_id=repo_id,
                        file_path=file_path,
                        symbol_name=symbol.name,
                        symbol_type=symbol.symbol_type.value,
                        start_line=symbol.start_line,
                        end_line=symbol.end_line,
                        content=content,
                        token_count=token_count,
                        metadata={
                            "language": ast_result.language,
                            "parent_symbol": symbol.parent_symbol,
                            "docstring": symbol.docstring,
                            "signature": symbol.signature,
                        },
                    )
                )
            else:
                # For oversized symbols (large class or lengthy function), slice into sub-windows
                lines = symbol.body_text.splitlines(keepends=True)
                window_size = 50  # 50 lines per sub-window
                overlap = 10     # 10 lines overlap

                step = max(1, window_size - overlap)
                for w_idx, start_idx in enumerate(range(0, len(lines), step)):
                    end_idx = min(len(lines), start_idx + window_size)
                    sub_body = "".join(lines[start_idx:end_idx])
                    actual_start = symbol.start_line + start_idx
                    actual_end = symbol.start_line + end_idx - 1

                    sub_symbol = ParsedCodeSymbol(
                        name=f"{symbol.name} [part {w_idx + 1}]",
                        symbol_type=symbol.symbol_type,
                        start_line=actual_start,
                        end_line=actual_end,
                        signature=symbol.signature,
                        docstring=symbol.docstring,
                        body_text=sub_body,
                        parent_symbol=symbol.name,
                    )

                    sub_content = self._format_chunk_content(file_path, sub_symbol, ast_result.language)
                    sub_chunk_id = self.generate_chunk_id(
                        repo_id, file_path, actual_start, actual_end
                    )

                    chunks.append(
                        CodeChunk(
                            chunk_id=sub_chunk_id,
                            repo_id=repo_id,
                            file_path=file_path,
                            symbol_name=sub_symbol.name,
                            symbol_type=symbol.symbol_type.value,
                            start_line=actual_start,
                            end_line=actual_end,
                            content=sub_content,
                            token_count=self.estimate_tokens(sub_content),
                            metadata={
                                "language": ast_result.language,
                                "parent_symbol": symbol.name,
                                "is_partial": True,
                            },
                        )
                    )

                    if end_idx >= len(lines):
                        break

        return chunks

    def chunk_repository(
        self, repo_id: str, file_map: dict[str, str]
    ) -> ChunkingSummary:
        """Chunk an entire repository given a mapping of {relative_path: source_code}."""
        all_chunks: List[CodeChunk] = []

        for rel_path, content in file_map.items():
            file_chunks = self.chunk_file(repo_id, rel_path, content)
            all_chunks.extend(file_chunks)

        total_tokens = sum(c.token_count for c in all_chunks)
        avg_tokens = round(total_tokens / len(all_chunks), 1) if all_chunks else 0.0

        return ChunkingSummary(
            repo_id=repo_id,
            total_files_chunked=len(file_map),
            total_chunks=len(all_chunks),
            total_tokens=total_tokens,
            average_chunk_size_tokens=avg_tokens,
            chunks=all_chunks,
        )


semantic_chunker_service = SemanticChunkerService()
