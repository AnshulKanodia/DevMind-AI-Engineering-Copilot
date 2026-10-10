from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievedChunk


class QACitation(BaseModel):
    """Detailed metadata for a cited code reference."""

    citation_label: str = Field(
        ...,
        description="Standard citation identifier e.g. 'app/services/auth.py:25-50'",
        examples=["app/core/security.py:10-35"],
    )
    file_path: str = Field(..., description="Relative file path in repository")
    start_line: int = Field(..., description="1-indexed starting line")
    end_line: int = Field(..., description="1-indexed ending line")
    symbol_name: Optional[str] = Field(
        default=None, description="Enclosing class, function or method name"
    )
    snippet: Optional[str] = Field(
        default=None, description="Truncated code snippet preview"
    )


class QARequest(BaseModel):
    """Request payload for grounded codebase Q&A."""

    repo_id: str = Field(..., description="Repository identifier")
    query: str = Field(..., description="Developer question about the codebase")
    top_k: int = Field(
        default=5, ge=1, le=20, description="Number of top chunks to retrieve"
    )
    alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Dense vs sparse weighting (1.0 = pure vector, 0.0 = pure BM25)",
    )
    file_path_filter: Optional[str] = Field(
        default=None, description="Optional single file filter"
    )


class QAResponse(BaseModel):
    """Grounded answer with citations and retrieved context."""

    repo_id: str
    query: str
    answer: str
    citations: List[str] = Field(
        default_factory=list,
        description="List of citation tags e.g. ['app/main.py:12-30']",
    )
    detailed_citations: List[QACitation] = Field(
        default_factory=list,
        description="Structured source metadata for cited chunks",
    )
    retrieved_chunks: List[RetrievedChunk] = Field(
        default_factory=list,
        description="Source chunks fed to the LLM context",
    )
    model_used: str = Field(default="gpt-4o", description="Model name that synthesized the answer")
    is_grounded: bool = Field(
        default=True,
        description="Whether the response is strictly grounded in retrieved code",
    )
