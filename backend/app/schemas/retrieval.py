from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HybridSearchQuery(BaseModel):
    repo_id: str = Field(..., description="Target repository identifier")
    query: str = Field(..., description="Developer question or keyword query")
    top_k: int = Field(5, ge=1, le=50, description="Number of chunks to return")
    alpha: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Weighting between dense vector (1.0) and sparse BM25 (0.0)",
    )
    file_path_filter: Optional[str] = Field(None, description="Optional filter targeting a specific file")


class RetrievedChunk(BaseModel):
    chunk_id: str
    file_path: str
    symbol_name: Optional[str] = None
    start_line: int
    end_line: int
    content: str
    combined_score: float
    dense_score: float
    sparse_score: float
    citation_label: str = Field(..., description="Formatted reference tag (e.g., auth.py:45-52)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HybridSearchResponse(BaseModel):
    repo_id: str
    query: str
    total_results: int
    chunks: List[RetrievedChunk]
