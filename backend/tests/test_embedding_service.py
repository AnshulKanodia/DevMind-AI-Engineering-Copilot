import math
import pytest
from app.schemas.chunk import CodeChunk
from app.services.embedding_service import embedding_service


def test_synthetic_vector_normalization_and_dimensions():
    vec = embedding_service._generate_synthetic_vector("test query", dimensions=1536)
    assert len(vec) == 1536

    # Unit norm test: sum(x^2) should be approximately 1.0
    magnitude = math.sqrt(sum(x * x for x in vec))
    assert abs(magnitude - 1.0) < 0.01


@pytest.mark.asyncio
async def test_embed_chunks_batching_and_cost():
    # Create 70 chunks (exceeding BATCH_SIZE=64 to test batch splitting)
    chunks = [
        CodeChunk(
            chunk_id=f"chunk_{i}",
            repo_id="test-repo",
            file_path=f"file_{i}.py",
            symbol_name=f"func_{i}",
            start_line=1,
            end_line=10,
            content=f"def func_{i}(): return {i}",
            token_count=15,
        )
        for i in range(70)
    ]

    result = await embedding_service.embed_chunks(chunks, force_mock=True)

    assert result.total_embedded == 70
    assert result.total_tokens == 70 * 15
    assert result.dimensions == 1536
    assert result.cost_estimate_usd > 0
    assert len(result.vectors) == 70


@pytest.mark.asyncio
async def test_embed_query_mock():
    query_vec = await embedding_service.embed_query("how is login handled?")
    assert len(query_vec) == 1536
    assert isinstance(query_vec[0], float)
