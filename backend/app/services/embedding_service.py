import asyncio
import hashlib
import math
import random
from typing import List, Optional
import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.chunk import CodeChunk
from app.schemas.embedding import BatchEmbeddingResult, EmbeddingVector

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class EmbeddingService:
    """Batched OpenAI embedding service with token counting and retry logic."""

    # Cost per 1,000 tokens for text-embedding-3-small ($0.02 / 1,000,000 tokens)
    PRICE_PER_1K_TOKENS = 0.00002
    BATCH_SIZE = 64

    def __init__(self):
        self.settings = get_settings()

    def _generate_synthetic_vector(self, text: str, dimensions: int = 1536) -> List[float]:
        """Generate a deterministic, unit-normalized vector for testing/offline mode."""
        # Use sha256 seed based on input text
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        raw = [rng.gauss(0, 1) for _ in range(dimensions)]
        norm = math.sqrt(sum(x * x for x in raw)) or 1.0
        return [round(x / norm, 6) for x in raw]

    async def _embed_batch_online(
        self, texts: List[str], model: str, dimensions: int, max_retries: int = 3
    ) -> List[List[float]]:
        """Call OpenAI embeddings API with exponential backoff retries."""
        headers = {
            "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": texts,
            "model": model,
            "dimensions": dimensions,
        }

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        OPENAI_EMBEDDINGS_URL, json=payload, headers=headers
                    )

                if response.status_code == 200:
                    data = response.json()
                    return [item["embedding"] for item in data["data"]]

                elif response.status_code in (429, 500, 503):
                    # Rate limit or transient error: backoff
                    wait_time = (2 ** attempt) + 0.5
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"OpenAI embedding API error: {response.text}",
                    )
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"OpenAI network error: {str(e)}",
                    )
                await asyncio.sleep(2 ** attempt)

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="OpenAI embedding request exceeded maximum retries.",
        )

    async def embed_chunks(
        self, chunks: List[CodeChunk], force_mock: bool = False
    ) -> BatchEmbeddingResult:
        """Batch-embed a list of code chunks."""
        if not chunks:
            return BatchEmbeddingResult(
                total_embedded=0,
                total_tokens=0,
                cost_estimate_usd=0.0,
                model=self.settings.OPENAI_EMBEDDING_MODEL,
                dimensions=self.settings.OPENAI_EMBEDDING_DIMENSIONS,
                vectors=[],
            )

        model = self.settings.OPENAI_EMBEDDING_MODEL
        dimensions = self.settings.OPENAI_EMBEDDING_DIMENSIONS
        is_mock = force_mock or self.settings.OPENAI_API_KEY.startswith("sk-placeholder") or not self.settings.OPENAI_API_KEY

        vectors: List[EmbeddingVector] = []
        total_tokens = sum(c.token_count for c in chunks)

        # Process in batches of BATCH_SIZE
        for i in range(0, len(chunks), self.BATCH_SIZE):
            batch = chunks[i : i + self.BATCH_SIZE]
            texts = [c.content for c in batch]

            if is_mock:
                batch_embeddings = [
                    self._generate_synthetic_vector(t, dimensions) for t in texts
                ]
            else:
                batch_embeddings = await self._embed_batch_online(texts, model, dimensions)

            for chunk, vec in zip(batch, batch_embeddings):
                vectors.append(
                    EmbeddingVector(
                        chunk_id=chunk.chunk_id,
                        vector=vec,
                        model=model,
                        dimensions=dimensions,
                        token_usage=chunk.token_count,
                    )
                )

        cost = round((total_tokens / 1000.0) * self.PRICE_PER_1K_TOKENS, 6)

        return BatchEmbeddingResult(
            total_embedded=len(vectors),
            total_tokens=total_tokens,
            cost_estimate_usd=cost,
            model=model,
            dimensions=dimensions,
            vectors=vectors,
        )

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single search query text for vector similarity matching."""
        is_mock = self.settings.OPENAI_API_KEY.startswith("sk-placeholder") or not self.settings.OPENAI_API_KEY
        if is_mock:
            return self._generate_synthetic_vector(
                query, self.settings.OPENAI_EMBEDDING_DIMENSIONS
            )

        result = await self._embed_batch_online(
            [query],
            self.settings.OPENAI_EMBEDDING_MODEL,
            self.settings.OPENAI_EMBEDDING_DIMENSIONS,
        )
        return result[0]


embedding_service = EmbeddingService()
