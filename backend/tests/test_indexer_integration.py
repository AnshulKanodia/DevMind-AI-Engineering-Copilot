import pytest
from pathlib import Path
from app.schemas.retrieval import HybridSearchQuery
from app.services.file_filter import file_filter_service
from app.services.semantic_chunker import semantic_chunker_service
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store_service
from app.services.hybrid_retriever import hybrid_retriever_service


SAMPLE_REPO = {
    "src/auth/jwt.py": """import jwt
SECRET = "test-secret"

def sign_token(user_id: str) -> str:
    \"\"\"Sign a JWT token with secret.\"\"\"
    return jwt.encode({"sub": user_id}, SECRET)

def verify_token(token: str) -> dict:
    \"\"\"Verify and decode JWT token.\"\"\"
    return jwt.decode(token, SECRET)
""",
    "src/billing/tax.py": """def calculate_vat(amount: float, rate: float = 0.2) -> float:
    \"\"\"Calculate value added tax.\"\"\"
    return amount * rate

def calculate_discount(price: float, discount_percent: float) -> float:
    return price * (1.0 - discount_percent)
""",
}


@pytest.mark.asyncio
async def test_end_to_end_indexer_and_retrieval_precision():
    repo_id = "test-full-indexing-repo"

    # Step 1: Semantic chunking
    chunk_summary = semantic_chunker_service.chunk_repository(repo_id, SAMPLE_REPO)
    assert chunk_summary.total_chunks >= 4

    # Verify functions are not cut off
    for c in chunk_summary.chunks:
        assert c.start_line > 0
        assert c.end_line >= c.start_line
        assert c.content.strip()

    # Step 2: Batch embeddings (mock mode)
    emb_result = await embedding_service.embed_chunks(chunk_summary.chunks, force_mock=True)
    assert len(emb_result.vectors) == chunk_summary.total_chunks

    # Step 3: Index in vector store and BM25
    await vector_store_service.index_chunks(repo_id, chunk_summary.chunks, emb_result.vectors)
    hybrid_retriever_service.register_repo_chunks(repo_id, chunk_summary.chunks)

    # Step 4: Test Precision on keyword query: sign_token
    query_1 = HybridSearchQuery(repo_id=repo_id, query="sign_token", top_k=1, alpha=0.3)
    res_1 = await hybrid_retriever_service.search(query_1)

    assert len(res_1.chunks) == 1
    assert res_1.chunks[0].file_path == "src/auth/jwt.py"
    assert "sign_token" in res_1.chunks[0].symbol_name or "sign_token" in res_1.chunks[0].content
    assert res_1.chunks[0].citation_label.startswith("src/auth/jwt.py:")

    # Step 5: Test Precision on billing query: calculate_vat
    query_2 = HybridSearchQuery(repo_id=repo_id, query="calculate_vat", top_k=1, alpha=0.3)
    res_2 = await hybrid_retriever_service.search(query_2)

    assert len(res_2.chunks) == 1
    assert res_2.chunks[0].file_path == "src/billing/tax.py"
    assert "calculate_vat" in res_2.chunks[0].symbol_name or "calculate_vat" in res_2.chunks[0].content
