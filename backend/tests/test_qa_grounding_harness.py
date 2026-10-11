import re
from typing import List
import pytest

from app.agents.graph import build_devmind_graph
from app.agents.state import create_initial_state
from app.schemas.chunk import CodeChunk
from app.schemas.qa import QACitation, QAResponse
from app.services.hybrid_retriever import hybrid_retriever_service
from app.services.qa_agent import qa_agent_service

CITATION_REGEX = re.compile(r"^([a-zA-Z0-9_\-\./\\]+):(\d+)-(\d+)$")


@pytest.fixture
def synthetic_repo_corpus() -> tuple[str, List[CodeChunk]]:
    """Build a realistic multi-file synthetic codebase corpus for grounding verification."""
    repo_id = "grounding-benchmark-repo"
    chunks = [
        CodeChunk(
            chunk_id="bench_chk_1",
            repo_id=repo_id,
            file_path="app/core/security.py",
            symbol_name="encrypt_oauth_token",
            start_line=18,
            end_line=34,
            content=(
                "def encrypt_oauth_token(raw_token: str) -> str:\n"
                "    cipher = Fernet(settings.ENCRYPTION_KEY.encode())\n"
                "    return cipher.encrypt(raw_token.encode()).decode()"
            ),
            token_count=28,
            metadata={"language": "python"},
        ),
        CodeChunk(
            chunk_id="bench_chk_2",
            repo_id=repo_id,
            file_path="app/core/security.py",
            symbol_name="decrypt_oauth_token",
            start_line=37,
            end_line=52,
            content=(
                "def decrypt_oauth_token(encrypted_token: str) -> str:\n"
                "    cipher = Fernet(settings.ENCRYPTION_KEY.encode())\n"
                "    return cipher.decrypt(encrypted_token.encode()).decode()"
            ),
            token_count=28,
            metadata={"language": "python"},
        ),
        CodeChunk(
            chunk_id="bench_chk_3",
            repo_id=repo_id,
            file_path="app/services/rate_limiter.py",
            symbol_name="check_user_quota",
            start_line=10,
            end_line=29,
            content=(
                "async def check_user_quota(user_id: str, limit: int = 100) -> bool:\n"
                "    current = await redis.incr(f'quota:{user_id}')\n"
                "    return current <= limit"
            ),
            token_count=26,
            metadata={"language": "python"},
        ),
        CodeChunk(
            chunk_id="bench_chk_4",
            repo_id=repo_id,
            file_path="app/api/v1/endpoints/webhooks.py",
            symbol_name="verify_github_signature",
            start_line=45,
            end_line=68,
            content=(
                "def verify_github_signature(payload: bytes, signature_header: str) -> bool:\n"
                "    mac = hmac.new(webhook_secret, msg=payload, digestmod=hashlib.sha256)\n"
                "    return hmac.compare_digest(f'sha256={mac.hexdigest()}', signature_header)"
            ),
            token_count=32,
            metadata={"language": "python"},
        ),
    ]
    hybrid_retriever_service.register_repo_chunks(repo_id, chunks)
    return repo_id, chunks


@pytest.mark.asyncio
async def test_citation_line_range_format_and_bounds(synthetic_repo_corpus):
    """Verify every emitted citation strictly adheres to 'filepath:start-end' with valid line numbers."""
    repo_id, chunks = synthetic_repo_corpus

    resp: QAResponse = await qa_agent_service.answer_query(
        repo_id=repo_id,
        query="How does encrypt_oauth_token encrypt tokens with Fernet?",
        top_k=3,
        force_offline=True,
    )

    assert resp.is_grounded is True
    assert len(resp.citations) > 0

    indexed_ranges = {
        f"{c.file_path}:{c.start_line}-{c.end_line}": (c.file_path, c.start_line, c.end_line)
        for c in chunks
    }

    for cite in resp.citations:
        match = CITATION_REGEX.match(cite)
        assert match is not None, f"Invalid citation format: {cite}"
        f_path, start_str, end_str = match.group(1), match.group(2), match.group(3)
        start_line, end_line = int(start_str), int(end_str)

        assert start_line >= 1
        assert end_line >= start_line
        # Ensure citation is strictly grounded in indexed corpus (no fabricated line ranges)
        assert cite in indexed_ranges
        assert indexed_ranges[cite] == (f_path, start_line, end_line)


@pytest.mark.asyncio
async def test_detailed_citations_schema_alignment(synthetic_repo_corpus):
    """Verify detailed_citations objects match retrieved chunk metadata and contain non-empty snippets."""
    repo_id, _ = synthetic_repo_corpus

    resp = await qa_agent_service.answer_query(
        repo_id=repo_id,
        query="How does verify_github_signature validate webhook HMAC?",
        top_k=2,
        force_offline=True,
    )

    assert len(resp.detailed_citations) == len(resp.citations)
    for dc in resp.detailed_citations:
        assert isinstance(dc, QACitation)
        assert dc.citation_label in resp.citations
        assert dc.start_line <= dc.end_line
        assert dc.snippet is not None and len(dc.snippet) > 0
        assert dc.file_path in dc.citation_label


@pytest.mark.asyncio
async def test_file_path_filter_strict_isolation(synthetic_repo_corpus):
    """Verify file_path_filter restricts retrieved chunks and citations exclusively to the target file."""
    repo_id, _ = synthetic_repo_corpus
    target_file = "app/services/rate_limiter.py"

    resp = await qa_agent_service.answer_query(
        repo_id=repo_id,
        query="How are tokens and user limits checked?",
        top_k=5,
        file_path_filter=target_file,
        force_offline=True,
    )

    assert resp.is_grounded is True
    assert len(resp.retrieved_chunks) == 1
    assert resp.retrieved_chunks[0].file_path == target_file
    for cite in resp.citations:
        assert cite.startswith(f"{target_file}:")


@pytest.mark.asyncio
async def test_hallucination_citaion_rejection(synthetic_repo_corpus):
    """Verify extract_citations rejects fabricated file paths or line ranges not present in retrieved chunks."""
    _, chunks = synthetic_repo_corpus
    retrieved_resp = await hybrid_retriever_service.search(
        params=qa_agent_service.format_context.__self__
        if False
        else __import__("app.schemas.retrieval", fromlist=["HybridSearchQuery"]).HybridSearchQuery(
            repo_id="grounding-benchmark-repo",
            query="encrypt_oauth_token",
            top_k=2,
        )
    )

    # Simulate an LLM output containing both a real citation and a hallucinated citation
    llm_output_with_hallucination = (
        "Token encryption is handled in `[app/core/security.py:18-34]` "
        "and also in `[app/core/nonexistent_ghost_file.py:99-150]`."
    )

    valid_citations = qa_agent_service.extract_citations(
        llm_output_with_hallucination,
        retrieved_resp.chunks,
    )

    assert "app/core/security.py:18-34" in valid_citations
    assert "app/core/nonexistent_ghost_file.py:99-150" not in valid_citations


@pytest.mark.asyncio
async def test_end_to_end_graph_qa_citation_footer_validation(synthetic_repo_corpus):
    """Verify full LangGraph execution appends formatted '**Sources & Citations:**' block with valid tags."""
    repo_id, _ = synthetic_repo_corpus
    graph = build_devmind_graph()

    state = create_initial_state(
        repo_id=repo_id,
        user_query="Explain how check_user_quota enforces rate limits in Redis",
    )
    final_state = await graph.execute(state)

    assert final_state["current_step"] == "completed"
    assert final_state["intent"] == "code_qa"
    assert "**Sources & Citations:**" in final_state["final_response"]
    assert "`app/services/rate_limiter.py:10-29`" in final_state["final_response"]
    assert final_state["metadata"]["is_grounded"] is True
