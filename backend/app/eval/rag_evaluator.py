from datetime import datetime, timezone
import math
import re
from typing import Any, Callable, Dict, List, Optional, Set

from app.eval.golden_dataset import GOLDEN_RAG_DATASET, get_golden_dataset
from app.eval.schemas import EvaluationQueryResult, GoldenQueryItem, RAGEvalReport


def normalize_path(path: str) -> str:
    """Standardize path separators and casing for consistent IR evaluation matching."""
    return path.replace("\\", "/").strip().lower()


def compute_recall_at_k(
    retrieved_files: List[str], expected_files: List[str], k: int = 5
) -> float:
    """Compute Recall@K: fraction of expected ground-truth files retrieved in top K.

    Recall@K = |Retrieved_k ∩ Expected| / |Expected|
    """
    if not expected_files:
        return 1.0

    retrieved_top_k: Set[str] = {normalize_path(p) for p in retrieved_files[:k]}
    expected_set: Set[str] = {normalize_path(p) for p in expected_files}

    intersection = retrieved_top_k.intersection(expected_set)
    return round(len(intersection) / len(expected_set), 4)


def compute_mrr(
    retrieved_files: List[str], expected_files: List[str], k: int = 5
) -> float:
    """Compute Mean Reciprocal Rank (MRR): 1 / rank of first relevant retrieved document.

    If first relevant file is at rank 1 -> 1.0; at rank 2 -> 0.5; none in top K -> 0.0.
    """
    if not expected_files:
        return 1.0

    expected_set: Set[str] = {normalize_path(p) for p in expected_files}
    for rank, file_path in enumerate(retrieved_files[:k], start=1):
        if normalize_path(file_path) in expected_set:
            return round(1.0 / rank, 4)

    return 0.0


def compute_dcg_at_k(relevances: List[int], k: int = 5) -> float:
    """Compute Discounted Cumulative Gain at K using standard exponential gain."""
    dcg = 0.0
    for i, rel in enumerate(relevances[:k], start=1):
        if rel > 0:
            dcg += (2**rel - 1) / math.log2(i + 1)
    return dcg


def compute_ndcg_at_k(
    retrieved_files: List[str], relevance_grades: Dict[str, int], k: int = 5
) -> float:
    """Compute Normalized Discounted Cumulative Gain (NDCG@K).

    NDCG@K = DCG@K / IDCG@K, where IDCG is the ideal DCG under perfect ranking.
    """
    norm_grades = {normalize_path(k): v for k, v in relevance_grades.items()}

    # Actual gains for retrieved files
    actual_relevances = [
        norm_grades.get(normalize_path(f), 0) for f in retrieved_files[:k]
    ]
    dcg = compute_dcg_at_k(actual_relevances, k=k)

    # Ideal ranking sorted descending by grade
    ideal_relevances = sorted(norm_grades.values(), reverse=True)[:k]
    idcg = compute_dcg_at_k(ideal_relevances, k=k)

    if idcg == 0.0:
        return 1.0 if dcg == 0.0 else 0.0

    return round(min(1.0, dcg / idcg), 4)


def compute_citation_precision(
    citations: List[Dict[str, Any]], expected_files: List[str]
) -> float:
    """Compute Citation Precision: fraction of generated citations anchored in expected files."""
    if not citations:
        return 1.0 if not expected_files else 0.0

    expected_set = {normalize_path(f) for f in expected_files}
    valid_citations = 0

    for cit in citations:
        file_path = cit.get("file", "") if isinstance(cit, dict) else getattr(cit, "file", "")
        if normalize_path(file_path) in expected_set:
            valid_citations += 1

    return round(valid_citations / len(citations), 4)


def compute_groundedness(answer: str, retrieved_chunks: List[str]) -> float:
    """Compute groundedness score: verifies answer content tokens are supported by retrieved context."""
    if not answer:
        return 0.0
    if not retrieved_chunks:
        return 0.5  # Neutral fallback

    context_words = set(re.findall(r"\b[a-zA-Z0-9_]{4,}\b", " ".join(retrieved_chunks).lower()))
    answer_words = re.findall(r"\b[a-zA-Z0-9_]{4,}\b", answer.lower())

    if not answer_words:
        return 1.0

    grounded_tokens = sum(1 for tok in answer_words if tok in context_words)
    ratio = grounded_tokens / len(answer_words)
    return round(min(1.0, max(0.0, ratio)), 4)


class RAGEvaluator:
    """Evaluation harness for measuring RAG retrieval accuracy and citation precision."""

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def evaluate_query(
        self,
        item: GoldenQueryItem,
        retrieved_files: List[str],
        citations: List[Dict[str, Any]],
        answer: str = "",
        retrieved_chunks: Optional[List[str]] = None,
    ) -> EvaluationQueryResult:
        """Score an individual query response against ground-truth expectations."""
        recall = compute_recall_at_k(retrieved_files, item.expected_files, k=self.top_k)
        mrr = compute_mrr(retrieved_files, item.expected_files, k=self.top_k)
        ndcg = compute_ndcg_at_k(retrieved_files, item.relevance_grades, k=self.top_k)
        citation_prec = compute_citation_precision(citations, item.expected_files)
        groundedness = compute_groundedness(answer, retrieved_chunks or [])

        return EvaluationQueryResult(
            query_id=item.query_id,
            query=item.query,
            category=item.category,
            retrieved_files=retrieved_files[: self.top_k],
            generated_citations=citations,
            recall_at_k=recall,
            reciprocal_rank=mrr,
            ndcg_at_5=ndcg,
            citation_precision=citation_prec,
            groundedness_score=groundedness,
        )

    def evaluate_benchmark(
        self,
        eval_fn: Callable[[str], Dict[str, Any]],
        dataset: Optional[List[GoldenQueryItem]] = None,
    ) -> RAGEvalReport:
        """Run the evaluation benchmark across the golden dataset using an inference/retrieval function."""
        items = dataset or get_golden_dataset()
        results: List[EvaluationQueryResult] = []
        category_metrics: Dict[str, Dict[str, List[float]]] = {}

        for item in items:
            out = eval_fn(item.query)
            retrieved_files = out.get("retrieved_files", [])
            citations = out.get("citations", [])
            answer = out.get("answer", "")
            chunks = out.get("chunks", [])

            res = self.evaluate_query(
                item=item,
                retrieved_files=retrieved_files,
                citations=citations,
                answer=answer,
                retrieved_chunks=chunks,
            )
            results.append(res)

            # Accumulate category breakdown
            cat = item.category
            if cat not in category_metrics:
                category_metrics[cat] = {
                    "recall": [],
                    "mrr": [],
                    "ndcg": [],
                    "precision": [],
                }
            category_metrics[cat]["recall"].append(res.recall_at_k)
            category_metrics[cat]["mrr"].append(res.reciprocal_rank)
            category_metrics[cat]["ndcg"].append(res.ndcg_at_5)
            category_metrics[cat]["precision"].append(res.citation_precision)

        total = len(results)
        mean_recall = sum(r.recall_at_k for r in results) / total if total else 0.0
        mean_mrr = sum(r.reciprocal_rank for r in results) / total if total else 0.0
        mean_ndcg = sum(r.ndcg_at_5 for r in results) / total if total else 0.0
        mean_precision = sum(r.citation_precision for r in results) / total if total else 0.0
        mean_groundedness = sum(r.groundedness_score for r in results) / total if total else 0.0

        breakdowns: Dict[str, Dict[str, float]] = {}
        for cat, metric_lists in category_metrics.items():
            breakdowns[cat] = {
                "mean_recall": round(sum(metric_lists["recall"]) / len(metric_lists["recall"]), 4),
                "mean_mrr": round(sum(metric_lists["mrr"]) / len(metric_lists["mrr"]), 4),
                "mean_ndcg": round(sum(metric_lists["ndcg"]) / len(metric_lists["ndcg"]), 4),
                "mean_precision": round(sum(metric_lists["precision"]) / len(metric_lists["precision"]), 4),
            }

        return RAGEvalReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_queries=total,
            top_k=self.top_k,
            mean_recall_at_k=round(mean_recall, 4),
            mean_mrr=round(mean_mrr, 4),
            mean_ndcg_at_5=round(mean_ndcg, 4),
            mean_citation_precision=round(mean_precision, 4),
            mean_groundedness=round(mean_groundedness, 4),
            category_breakdowns=breakdowns,
            results=results,
        )


# Global Evaluator Singleton
rag_evaluator = RAGEvaluator()
