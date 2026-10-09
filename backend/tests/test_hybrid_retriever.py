import pytest
from app.schemas.chunk import CodeChunk
from app.schemas.embedding import EmbeddingVector
from app.schemas.retrieval import HybridSearchQuery
from app.services.hybrid_retriever import BM25Scorer, hybrid_retriever_service
from app.services.vector_store import vector_store_service


def test_bm25_tokenizer_camel_case():
    tokens = BM25Scorer.tokenize("processPayment(userId: string)")
    assert "process" in tokens
    assert "payment" in tokens
    assert "userid" in tokens


@pytest.mark.asyncio
async def test_hybrid_search_fusion_and_citation():
    repo_id = "test-hybrid-repo"

    chunk1 = CodeChunk(
        chunk_id="chk_auth",
        repo_id=repo_id,
        file_path="src/auth.ts",
        symbol_name="verifyJwtSecret",
        start_line=45,
        end_line=52,
        content="// File: src/auth.ts\nconst JWT_SECRET = process.env.JWT_SECRET;\nexport function verifyJwtSecret() {}",
        token_count=20,
    )
    chunk2 = CodeChunk(
        chunk_id="chk_calc",
        repo_id=repo_id,
        file_path="src/calc.ts",
        symbol_name="sum",
        start_line=10,
        end_line=15,
        content="// File: src/calc.ts\nexport function sum(a: number, b: number) { return a + b; }",
        token_count=15,
    )

    # Register in BM25
    hybrid_retriever_service.register_repo_chunks(repo_id, [chunk1, chunk2])

    # Register mock vectors in vector store
    emb1 = EmbeddingVector(
        chunk_id="chk_auth",
        vector=[0.8] * 1536,
        model="text-embedding-3-small",
        dimensions=1536,
    )
    emb2 = EmbeddingVector(
        chunk_id="chk_calc",
        vector=[0.1] * 1536,
        model="text-embedding-3-small",
        dimensions=1536,
    )
    await vector_store_service.index_chunks(repo_id, [chunk1, chunk2], [emb1, emb2])

    # Search for JWT keyword
    query = HybridSearchQuery(repo_id=repo_id, query="JWT_SECRET", top_k=2, alpha=0.5)
    resp = await hybrid_retriever_service.search(query)

    assert resp.total_results > 0
    top = resp.chunks[0]
    assert top.chunk_id == "chk_auth"
    assert top.citation_label == "src/auth.ts:45-52"
    assert top.sparse_score > 0
    assert top.combined_score > 0
