import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings
from app.schemas.qa import QACitation, QAResponse
from app.schemas.retrieval import HybridSearchQuery, RetrievedChunk
from app.services.hybrid_retriever import hybrid_retriever_service

logger = logging.getLogger("devmind.agents.qa")

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

QA_SYSTEM_PROMPT = """You are the DevMind Senior Codebase Q&A Agent.
Your job is to answer the developer's technical question based STRICTLY AND EXCLUSIVELY on the provided code context snippets below.

CRITICAL GROUNDING RULES:
1. ONLY make claims that are directly supported by the provided source code chunks.
2. DO NOT invent, assume, or hallucinate facts, functions, dependencies, or implementation details not present in the snippets.
3. If the provided context does NOT contain enough information to fully answer the query, clearly state: "Based on the indexed codebase, this information is not found in the provided context."
4. Whenever you reference logic, functions, classes, or configuration, explicitly cite the exact file and lines using the format `[filename:start_line-end_line]`.
5. Provide concise, high-precision code explanations with markdown formatting and inline code blocks when applicable.
"""


class QAAgentService:
    """Specialized agent service for grounded technical code Q&A with strict line citations."""

    def __init__(self):
        self.settings = get_settings()

    def format_context(self, chunks: List[RetrievedChunk]) -> str:
        """Format retrieved code chunks into structured numbered context blocks."""
        if not chunks:
            return "No relevant code snippets were found in the codebase index."

        blocks: List[str] = []
        for idx, chunk in enumerate(chunks, 1):
            symbol = f" (Symbol: `{chunk.symbol_name}`)" if chunk.symbol_name else ""
            header = (
                f"### [Source #{idx}] File: `{chunk.file_path}` "
                f"(Lines {chunk.start_line}-{chunk.end_line}){symbol}\n"
                f"Citation Tag: `[{chunk.citation_label}]`"
            )
            lang = chunk.metadata.get("language", "") if chunk.metadata else ""
            code_block = f"```{lang}\n{chunk.content}\n```"
            blocks.append(f"{header}\n{code_block}")

        return "\n\n".join(blocks)

    def extract_citations(
        self, text: str, chunks: List[RetrievedChunk]
    ) -> List[str]:
        """Extract explicit citation references from text or map from retrieved chunks."""
        # Match pattern [path/to/file.ext:start-end] or `path/to/file.ext:start-end`
        found_cites = set(re.findall(r"\[([a-zA-Z0-9_\-\./\\]+:\d+\-\d+)\]", text))
        found_cites.update(re.findall(r"`([a-zA-Z0-9_\-\./\\]+:\d+\-\d+)`", text))

        # Check against chunk citation labels
        valid_labels = {c.citation_label for c in chunks}
        matched = [c for c in found_cites if c in valid_labels]

        # If LLM didn't format tags identically, default to the top retrieved chunks used in context
        if not matched and chunks:
            matched = [c.citation_label for c in chunks[:3]]

        return sorted(list(set(matched)))

    def _build_detailed_citations(
        self, citation_labels: List[str], chunks: List[RetrievedChunk]
    ) -> List[QACitation]:
        """Build structured citation models from matched citation labels and chunk metadata."""
        chunk_map = {c.citation_label: c for c in chunks}
        detailed: List[QACitation] = []

        for label in citation_labels:
            chunk = chunk_map.get(label)
            if chunk:
                snippet = chunk.content[:150] + "..." if len(chunk.content) > 150 else chunk.content
                detailed.append(
                    QACitation(
                        citation_label=label,
                        file_path=chunk.file_path,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        symbol_name=chunk.symbol_name,
                        snippet=snippet.strip(),
                    )
                )

        return detailed

    def _mock_grounded_answer(
        self, query: str, chunks: List[RetrievedChunk]
    ) -> str:
        """Deterministic, grounded answer synthesizer for offline testing or placeholder API keys."""
        if not chunks:
            return (
                "Based on the indexed codebase, this information is not found in the provided context. "
                "No matching code symbols or files were retrieved for this query."
            )

        top_chunk = chunks[0]
        summary_lines = [
            f"Based on the codebase analysis for query: *\"{query}\"*:\n",
            f"Relevant implementation found in `{top_chunk.file_path}` lines {top_chunk.start_line}-{top_chunk.end_line} "
            f"(`[{top_chunk.citation_label}]`):",
            f"\n```{top_chunk.metadata.get('language', 'text')}\n{top_chunk.content}\n```",
        ]

        if top_chunk.symbol_name:
            summary_lines.append(
                f"\nThe logic is defined in symbol `{top_chunk.symbol_name}`."
            )

        if len(chunks) > 1:
            additional_cites = [f"`[{c.citation_label}]`" for c in chunks[1:3]]
            summary_lines.append(
                f"\nAdditional supporting references: {', '.join(additional_cites)}."
            )

        return "\n".join(summary_lines)

    async def answer_query(
        self,
        repo_id: str,
        query: str,
        top_k: int = 5,
        alpha: float = 0.5,
        file_path_filter: Optional[str] = None,
        force_offline: bool = False,
    ) -> QAResponse:
        """Execute grounded Code Q&A against repository vectors and code chunks."""
        # 1. Retrieve most relevant context chunks via Hybrid Retriever
        search_query = HybridSearchQuery(
            repo_id=repo_id,
            query=query,
            top_k=top_k,
            alpha=alpha,
            file_path_filter=file_path_filter,
        )
        search_resp = await hybrid_retriever_service.search(params=search_query)
        chunks = search_resp.chunks

        # If no chunks found, return immediate ungrounded notification
        if not chunks:
            answer = (
                "Based on the indexed codebase, this information is not found in the provided context. "
                "No matching code symbols or files were retrieved for this query."
            )
            return QAResponse(
                repo_id=repo_id,
                query=query,
                answer=answer,
                citations=[],
                detailed_citations=[],
                retrieved_chunks=[],
                model_used="deterministic-grounder",
                is_grounded=False,
            )

        # 2. Check offline mode or placeholder API key
        is_mock = (
            force_offline
            or not self.settings.OPENAI_API_KEY
            or self.settings.OPENAI_API_KEY.startswith("sk-placeholder")
        )

        if is_mock:
            answer = self._mock_grounded_answer(query, chunks)
            citations = self.extract_citations(answer, chunks)
            detailed = self._build_detailed_citations(citations, chunks)
            return QAResponse(
                repo_id=repo_id,
                query=query,
                answer=answer,
                citations=citations,
                detailed_citations=detailed,
                retrieved_chunks=chunks,
                model_used="deterministic-grounder",
                is_grounded=True,
            )

        # 3. Call OpenAI LLM with grounded prompt context
        formatted_context = self.format_context(chunks)
        user_prompt = (
            f"Developer Query:\n{query}\n\n"
            f"Codebase Context Snippets:\n{formatted_context}\n\n"
            f"Please answer the query thoroughly, citing relevant code locations using [filename:start_line-end_line]."
        )

        headers = {
            "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": QA_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(OPENAI_CHAT_URL, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                answer = data["choices"][0]["message"]["content"]
                citations = self.extract_citations(answer, chunks)
                detailed = self._build_detailed_citations(citations, chunks)

                return QAResponse(
                    repo_id=repo_id,
                    query=query,
                    answer=answer,
                    citations=citations,
                    detailed_citations=detailed,
                    retrieved_chunks=chunks,
                    model_used=self.settings.OPENAI_MODEL,
                    is_grounded=True,
                )
            else:
                logger.warning(
                    f"OpenAI Q&A failed with status {resp.status_code}, falling back to mock grounding."
                )
        except Exception as e:
            logger.warning(f"Error calling OpenAI Q&A API: {e}, falling back to mock grounding.")

        # Fallback on API failure
        answer = self._mock_grounded_answer(query, chunks)
        citations = self.extract_citations(answer, chunks)
        detailed = self._build_detailed_citations(citations, chunks)

        return QAResponse(
            repo_id=repo_id,
            query=query,
            answer=answer,
            citations=citations,
            detailed_citations=detailed,
            retrieved_chunks=chunks,
            model_used="fallback-grounder",
            is_grounded=True,
        )


qa_agent_service = QAAgentService()
