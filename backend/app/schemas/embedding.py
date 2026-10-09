from typing import List
from pydantic import BaseModel, Field


class EmbeddingVector(BaseModel):
    chunk_id: str = Field(..., description="Target code chunk identifier")
    vector: List[float] = Field(..., description="Normalized dense embedding vector")
    model: str = Field(..., description="Embedding model name (e.g. text-embedding-3-small)")
    dimensions: int = Field(..., description="Length of the embedding vector")
    token_usage: int = Field(0, description="Tokens consumed to embed this chunk")


class BatchEmbeddingResult(BaseModel):
    total_embedded: int
    total_tokens: int
    cost_estimate_usd: float
    model: str
    dimensions: int
    vectors: List[EmbeddingVector]
