from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GoldenQueryItem(BaseModel):
    """Ground-truth evaluation item representing a developer query with expected artifacts."""

    query_id: str = Field(..., description="Unique identifier for the test query")
    query: str = Field(..., description="Natural language developer query")
    category: str = Field(..., description="Functional category (Architecture, Security, etc.)")
    expected_files: List[str] = Field(..., description="Ground-truth file paths that must be retrieved")
    expected_lines: Optional[Dict[str, str]] = Field(default=None, description="Expected line range hints")
    ground_truth_answer: str = Field(..., description="Reference ground-truth answer summary")
    relevance_grades: Dict[str, int] = Field(
        ..., description="Relevance grades (0-3) for NDCG computation"
    )


class EvaluationQueryResult(BaseModel):
    """Detailed evaluation score breakdown for a single test query."""

    query_id: str
    query: str
    category: str
    retrieved_files: List[str]
    generated_citations: List[Dict[str, Any]]
    recall_at_k: float
    reciprocal_rank: float
    ndcg_at_5: float
    citation_precision: float
    groundedness_score: float


class RAGEvalReport(BaseModel):
    """Comprehensive benchmark evaluation report across the entire Golden Dataset."""

    timestamp: str
    total_queries: int
    top_k: int
    mean_recall_at_k: float
    mean_mrr: float
    mean_ndcg_at_5: float
    mean_citation_precision: float
    mean_groundedness: float
    category_breakdowns: Dict[str, Dict[str, float]]
    results: List[EvaluationQueryResult]
