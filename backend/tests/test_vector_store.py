import pytest
from app.schemas.chunk import CodeChunk
from app.schemas.embedding import EmbeddingVector
from app.services.vector_store import vector_store_service


def test_atlas_vector_index_spec():
    spec = vector_store_service.get_atlas_vector_index_spec()
    assert "fields" in spec
    fields = {f["path"]: f for f in spec["fields"]}
    assert "embedding" in fields
    assert fields["embedding"]["type"] == "vector"
    assert fields["embedding"]["similarity"] == "cosine"
    assert "repo_id" in fields
    assert fields["repo_id"]["type"] == "filter"


def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert vector_store_service.cosine_similarity(v1, v2) == 1.0
    assert vector_store_service.cosine_similarity(v1, v3) == 0.0


@pytest.mark.asyncio
async def test_indexing_and_vector_search():
    repo_id = "test-vector-repo"

    chunk1 = CodeChunk(
        chunk_id="c1",
        repo_id=repo_id,
        file_path="auth.py",
        symbol_name="login",
        start_line=1,
        end_line=10,
        content="def login(): verify_password()",
        token_count=10,
    )
    chunk2 = CodeChunk(
        chunk_id="c2",
        repo_id=repo_id,
        file_path="pay.py",
        symbol_name="charge",
        start_line=1,
        end_line=10,
        content="def charge(): stripe.pay()",
        token_count=10,
    )

    # Distinct vectors
    emb1 = EmbeddingVector(
        chunk_id="c1",
        vector=[0.9, 0.1] + [0.0] * 1534,
        model="text-embedding-3-small",
        dimensions=1536,
    )
    emb2 = EmbeddingVector(
        chunk_id="c2",
        vector=[0.1, 0.9] + [0.0] * 1534,
        model="text-embedding-3-small",
        dimensions=1536,
    )

    indexed_count = await vector_store_service.index_chunks(
        repo_id, [chunk1, chunk2], [emb1, emb2]
    )
    assert indexed_count == 2

    # Query close to c1
    query_vec = [0.95, 0.05] + [0.0] * 1534
    results = await vector_store_service.vector_search(repo_id, query_vec, top_k=1)

    assert len(results) == 1
    assert results[0].chunk_id == "c1"
    assert results[0].symbol_name == "login"
    assert results[0].score > 0.8
