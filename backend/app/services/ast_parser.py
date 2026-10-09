import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.schemas.ast_nodes import CodeSymbolType, ParsedCodeSymbol, ParsedFileAST


class ASTParserService:
    """Language-aware AST parser extracting classes, functions, methods, and interfaces."""

    LANGUAGE_MAP: Dict[str, str] = {
        ".py": "python",
        ".pyw": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".go": "go",
        ".java": "java",
        ".kt": "kotlin",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
    }

    def detect_language(self, file_path: str) -> str:
        """Infer language by file extension."""
        ext = Path(file_path).suffix.lower()
        return self.LANGUAGE_MAP.get(ext, "unknown")

    def _extract_lines(self, lines: List[str], start_line: int, end_line: int) -> str:
        """Extract slice of lines (1-indexed inclusive)."""
        s_idx = max(0, start_line - 1)
        e_idx = min(len(lines), end_line)
        return "".join(lines[s_idx:e_idx])

    # -------------------------------------------------------------------------
    # Python AST Parser (Standard Library ast)
    # -------------------------------------------------------------------------
    def _parse_python(self, source_code: str, lines: List[str]) -> List[ParsedCodeSymbol]:
        """Parse Python source code using native ast module."""
        symbols: List[ParsedCodeSymbol] = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            # Fall back to structural parsing if syntax is invalid/incomplete
            return self._parse_generic_blocks(lines, "python")

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                c_start = getattr(node, "lineno", 1)
                c_end = getattr(node, "end_lineno", len(lines))
                doc = ast.get_docstring(node)
                sig = f"class {node.name}"
                body = self._extract_lines(lines, c_start, c_end)

                symbols.append(
                    ParsedCodeSymbol(
                        name=node.name,
                        symbol_type=CodeSymbolType.CLASS,
                        start_line=c_start,
                        end_line=c_end,
                        signature=sig,
                        docstring=doc,
                        body_text=body,
                        parent_symbol=None,
                    )
                )

                # Traverse methods within class body
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_start = getattr(item, "lineno", c_start)
                        m_end = getattr(item, "end_lineno", m_start)
                        m_doc = ast.get_docstring(item)
                        is_async = isinstance(item, ast.AsyncFunctionDef)
                        m_type = CodeSymbolType.ASYNC_FUNCTION if is_async else CodeSymbolType.METHOD
                        m_sig = f"{'async ' if is_async else ''}def {item.name}"
                        m_body = self._extract_lines(lines, m_start, m_end)

                        symbols.append(
                            ParsedCodeSymbol(
                                name=f"{node.name}.{item.name}",
                                symbol_type=m_type,
                                start_line=m_start,
                                end_line=m_end,
                                signature=m_sig,
                                docstring=m_doc,
                                body_text=m_body,
                                parent_symbol=node.name,
                            )
                        )

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                f_start = getattr(node, "lineno", 1)
                f_end = getattr(node, "end_lineno", len(lines))
                doc = ast.get_docstring(node)
                is_async = isinstance(node, ast.AsyncFunctionDef)
                f_type = CodeSymbolType.ASYNC_FUNCTION if is_async else CodeSymbolType.FUNCTION
                sig = f"{'async ' if is_async else ''}def {node.name}"
                body = self._extract_lines(lines, f_start, f_end)

                symbols.append(
                    ParsedCodeSymbol(
                        name=node.name,
                        symbol_type=f_type,
                        start_line=f_start,
                        end_line=f_end,
                        signature=sig,
                        docstring=doc,
                        body_text=body,
                        parent_symbol=None,
                    )
                )

        return symbols

    # -------------------------------------------------------------------------
    # TypeScript / JavaScript Grammar Parser
    # -------------------------------------------------------------------------
    def _find_matching_brace_end(self, lines: List[str], start_idx: int) -> int:
        """Find ending line index of a curly brace block."""
        brace_count = 0
        started = False

        for i in range(start_idx, len(lines)):
            line = lines[i]
            # Strip comments and strings roughly
            cleaned = re.sub(r"//.*$", "", line)
            cleaned = re.sub(r'(".*?"|\'.*?\'|`.*?`)', "", cleaned)

            for char in cleaned:
                if char == "{":
                    brace_count += 1
                    started = True
                elif char == "}":
                    brace_count -= 1
                    if started and brace_count == 0:
                        return i + 1  # 1-indexed end line

        return len(lines)

    def _parse_typescript_javascript(self, lines: List[str], lang: str) -> List[ParsedCodeSymbol]:
        """Parse TypeScript and JavaScript for classes, interfaces, and functions."""
        symbols: List[ParsedCodeSymbol] = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            line_no = i + 1

            # 1. Match Class
            class_match = re.search(r"^(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_$]+)", line)
            if class_match:
                name = class_match.group(1)
                end_line = self._find_matching_brace_end(lines, i)
                body = self._extract_lines(lines, line_no, end_line)
                symbols.append(
                    ParsedCodeSymbol(
                        name=name,
                        symbol_type=CodeSymbolType.CLASS,
                        start_line=line_no,
                        end_line=end_line,
                        signature=line,
                        body_text=body,
                    )
                )
                i = max(i + 1, end_line - 1)
                continue

            # 2. Match Interface
            interface_match = re.search(r"^(?:export\s+)?interface\s+([A-Za-z0-9_$]+)", line)
            if interface_match:
                name = interface_match.group(1)
                end_line = self._find_matching_brace_end(lines, i)
                body = self._extract_lines(lines, line_no, end_line)
                symbols.append(
                    ParsedCodeSymbol(
                        name=name,
                        symbol_type=CodeSymbolType.INTERFACE,
                        start_line=line_no,
                        end_line=end_line,
                        signature=line,
                        body_text=body,
                    )
                )
                i = max(i + 1, end_line - 1)
                continue

            # 3. Match Standard function: function foo(...)
            func_match = re.search(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*([A-Za-z0-9_$]+)", line)
            if func_match:
                name = func_match.group(1)
                is_async = "async " in line
                end_line = self._find_matching_brace_end(lines, i)
                body = self._extract_lines(lines, line_no, end_line)
                symbols.append(
                    ParsedCodeSymbol(
                        name=name,
                        symbol_type=CodeSymbolType.ASYNC_FUNCTION if is_async else CodeSymbolType.FUNCTION,
                        start_line=line_no,
                        end_line=end_line,
                        signature=line,
                        body_text=body,
                    )
                )
                i = max(i + 1, end_line - 1)
                continue

            # 4. Match Arrow function assignment: const foo = async (...) =>
            arrow_match = re.search(r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\(.*?\)\s*(?::\s*.*?)?\s*=>", line)
            if arrow_match:
                name = arrow_match.group(1)
                is_async = "async" in line
                end_line = self._find_matching_brace_end(lines, i) if "{" in line else line_no
                body = self._extract_lines(lines, line_no, end_line)
                symbols.append(
                    ParsedCodeSymbol(
                        name=name,
                        symbol_type=CodeSymbolType.ASYNC_FUNCTION if is_async else CodeSymbolType.FUNCTION,
                        start_line=line_no,
                        end_line=end_line,
                        signature=line,
                        body_text=body,
                    )
                )
                i = max(i + 1, end_line - 1)
                continue

            i += 1

        return symbols

    # -------------------------------------------------------------------------
    # Go Grammar Parser
    # -------------------------------------------------------------------------
    def _parse_go(self, lines: List[str]) -> List[ParsedCodeSymbol]:
        """Parse Go functions, methods, structs, and interfaces."""
        symbols: List[ParsedCodeSymbol] = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            line_no = i + 1

            # Struct / Interface: type Name struct { / type Name interface {
            type_match = re.search(r"^type\s+([A-Za-z0-9_]+)\s+(struct|interface)", line)
            if type_match:
                name = type_match.group(1)
                kind = type_match.group(2)
                stype = CodeSymbolType.STRUCT if kind == "struct" else CodeSymbolType.INTERFACE
                end_line = self._find_matching_brace_end(lines, i)
                body = self._extract_lines(lines, line_no, end_line)
                symbols.append(
                    ParsedCodeSymbol(
                        name=name,
                        symbol_type=stype,
                        start_line=line_no,
                        end_line=end_line,
                        signature=line,
                        body_text=body,
                    )
                )
                i = max(i + 1, end_line - 1)
                continue

            # Method with receiver: func (r *Receiver) MethodName(...)
            method_match = re.search(r"^func\s*\((?:[^)]+)\)\s*([A-Za-z0-9_]+)\s*\(", line)
            if method_match:
                name = method_match.group(1)
                end_line = self._find_matching_brace_end(lines, i)
                body = self._extract_lines(lines, line_no, end_line)
                symbols.append(
                    ParsedCodeSymbol(
                        name=name,
                        symbol_type=CodeSymbolType.METHOD,
                        start_line=line_no,
                        end_line=end_line,
                        signature=line,
                        body_text=body,
                    )
                )
                i = max(i + 1, end_line - 1)
                continue

            # Top-level Function: func FunctionName(...)
            func_match = re.search(r"^func\s+([A-Za-z0-9_]+)\s*\(", line)
            if func_match:
                name = func_match.group(1)
                end_line = self._find_matching_brace_end(lines, i)
                body = self._extract_lines(lines, line_no, end_line)
                symbols.append(
                    ParsedCodeSymbol(
                        name=name,
                        symbol_type=CodeSymbolType.FUNCTION,
                        start_line=line_no,
                        end_line=end_line,
                        signature=line,
                        body_text=body,
                    )
                )
                i = max(i + 1, end_line - 1)
                continue

            i += 1

        return symbols

    # -------------------------------------------------------------------------
    # Java Grammar Parser
    # -------------------------------------------------------------------------
    def _parse_java(self, lines: List[str]) -> List[ParsedCodeSymbol]:
        """Parse Java classes, interfaces, and methods."""
        symbols: List[ParsedCodeSymbol] = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            line_no = i + 1

            # Class or Interface
            class_match = re.search(r"(?:public|protected|private|static|\s)*\s+(?:class|interface|enum)\s+([A-Za-z0-9_]+)", line)
            if class_match and not line.endswith(";"):
                name = class_match.group(1)
                end_line = self._find_matching_brace_end(lines, i)
                body = self._extract_lines(lines, line_no, end_line)
                symbols.append(
                    ParsedCodeSymbol(
                        name=name,
                        symbol_type=CodeSymbolType.CLASS,
                        start_line=line_no,
                        end_line=end_line,
                        signature=line,
                        body_text=body,
                    )
                )
                i = max(i + 1, end_line - 1)
                continue

            i += 1

        return symbols

    # -------------------------------------------------------------------------
    # Generic Block Chunking (Fallback for other languages or script files)
    # -------------------------------------------------------------------------
    def _parse_generic_blocks(self, lines: List[str], lang: str) -> List[ParsedCodeSymbol]:
        """Fallback to chunk by contiguous non-empty code blocks."""
        symbols: List[ParsedCodeSymbol] = []
        chunk_size = 40  # 40-line blocks with context
        total = len(lines)

        for idx, start_l in enumerate(range(1, total + 1, chunk_size), start=1):
            end_l = min(total, start_l + chunk_size - 1)
            body = self._extract_lines(lines, start_l, end_l)
            if body.strip():
                symbols.append(
                    ParsedCodeSymbol(
                        name=f"block_{idx}",
                        symbol_type=CodeSymbolType.BLOCK,
                        start_line=start_l,
                        end_line=end_l,
                        signature=f"Lines {start_l}-{end_l}",
                        body_text=body,
                    )
                )
        return symbols

    # -------------------------------------------------------------------------
    # Unified Entrypoint
    # -------------------------------------------------------------------------
    def parse_file(self, file_path: str, source_code: str) -> ParsedFileAST:
        """Parse source code file into a structured AST representation."""
        lang = self.detect_language(file_path)
        lines = source_code.splitlines(keepends=True)
        if not lines:
            return ParsedFileAST(
                file_path=file_path,
                language=lang,
                total_symbols=0,
                total_lines=0,
                symbols=[],
            )

        if lang == "python":
            symbols = self._parse_python(source_code, lines)
        elif lang in ("typescript", "javascript"):
            symbols = self._parse_typescript_javascript(lines, lang)
        elif lang == "go":
            symbols = self._parse_go(lines)
        elif lang == "java":
            symbols = self._parse_java(lines)
        else:
            symbols = self._parse_generic_blocks(lines, lang)

        # If language parser found no specific high-level symbols, fall back to structural blocks
        if not symbols and len(lines) > 0:
            symbols = self._parse_generic_blocks(lines, lang)

        return ParsedFileAST(
            file_path=file_path,
            language=lang,
            total_symbols=len(symbols),
            total_lines=len(lines),
            symbols=symbols,
        )


ast_parser_service = ASTParserService()
