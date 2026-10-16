import pytest
from fastapi.testclient import TestClient

from app.eval.golden_dataset import GOLDEN_RAG_DATASET, get_golden_dataset
from app.eval.rag_evaluator import (
    compute_citation_precision,
    compute_groundedness,
    compute_mrr,
    compute_ndcg_at_k,
    compute_recall_at_k,
    rag_evaluator,
)
from app.eval.schemas import GoldenQueryItem
from app.main import app


def test_golden_dataset_structure():
    """Verify golden dataset contains required number of queries and complete metadata."""
    dataset = get_golden_dataset()
    assert len(dataset) >= 15

    for item in dataset:
        assert isinstance(item, GoldenQueryItem)
        assert item.query_id != ""
        assert len(item.expected_files) >= 1
        assert len(item.relevance_grades) >= 1
        assert item.ground_truth_answer != ""


def test_compute_recall_at_k():
    """Verify Recall@K mathematical calculation."""
    expected = ["app/auth.py", "app/user.py"]

    # All retrieved
    assert compute_recall_at_k(["app/auth.py", "app/user.py", "app/other.py"], expected, k=3) == 1.0
    # Half retrieved
    assert compute_recall_at_k(["app/auth.py", "app/other.py"], expected, k=2) == 0.5
    # None retrieved
    assert compute_recall_at_k(["app/random.py"], expected, k=5) == 0.0
    # Outside top k cutoff
    assert compute_recall_at_k(["app/noise.py", "app/auth.py", "app/user.py"], expected, k=1) == 0.0


def test_compute_mrr():
    """Verify Mean Reciprocal Rank (MRR) calculation."""
    expected = ["app/target.py"]

    # Rank 1 -> 1/1 = 1.0
    assert compute_mrr(["app/target.py", "app/other.py"], expected, k=5) == 1.0
    # Rank 2 -> 1/2 = 0.5
    assert compute_mrr(["app/noise.py", "app/target.py"], expected, k=5) == 0.5
    # Rank 4 -> 1/4 = 0.25
    assert compute_mrr(["a", "b", "c", "app/target.py"], expected, k=5) == 0.25
    # Not found in top K -> 0.0
    assert compute_mrr(["a", "b"], expected, k=2) == 0.0


def test_compute_ndcg_at_k():
    """Verify Normalized Discounted Cumulative Gain (NDCG@K) calculation."""
    grades = {"doc1": 3, "doc2": 2, "doc3": 1}

    # Perfect ranking
    assert compute_ndcg_at_k(["doc1", "doc2", "doc3"], grades, k=3) == 1.0

    # Suboptimal ranking
    ndcg_sub = compute_ndcg_at_k(["doc3", "doc2", "doc1"], grades, k=3)
    assert 0.0 < ndcg_sub < 1.0

    # Zero relevant retrieved
    assert compute_ndcg_at_k(["random1", "random2"], grades, k=2) == 0.0


def test_compute_citation_precision():
    """Verify citation precision calculation."""
    expected = ["app/service.py", "app/utils.py"]

    # All citations valid
    citations = [{"file": "app/service.py"}, {"file": "app/utils.py"}]
    assert compute_citation_precision(citations, expected) == 1.0

    # Half citations valid
    mixed = [{"file": "app/service.py"}, {"file": "app/wrong.py"}]
    assert compute_citation_precision(mixed, expected) == 0.5

    # Empty citations
    assert compute_citation_precision([], expected) == 0.0


def test_compute_groundedness():
    """Verify groundedness scoring between answer tokens and retrieved context."""
    chunks = ["The authentication module encrypts passwords using bcrypt hashing algorithm."]

    # High groundedness
    supported_answer = "Authentication module encrypts passwords with bcrypt hashing."
    assert compute_groundedness(supported_answer, chunks) >= 0.75

    # Low groundedness / unsupported claims
    hallucinated = "Quantum hyperdrive teleportation protocols are used for spacecraft."
    assert compute_groundedness(hallucinated, chunks) < 0.20


def test_full_benchmark_mock_evaluation():
    """Verify full benchmark evaluation passes quality thresholds across all golden queries."""
    dataset = get_golden_dataset()
    lookup = {i.query: i for i in dataset}

    def mock_high_quality_retriever(query: str):
        item = lookup[query]
        # Return expected files first, then 1 noise file
        files = list(item.expected_files) + ["app/noise.py"]
        citations = [{"file": f, "lines": "10-20"} for f in item.expected_files]
        return {
            "retrieved_files": files[:5],
            "citations": citations,
            "answer": item.ground_truth_answer,
            "chunks": [item.ground_truth_answer, "extra context"],
        }

    report = rag_evaluator.evaluate_benchmark(mock_high_quality_retriever, dataset=dataset)

    assert report.total_queries >= 15
    assert report.mean_recall_at_k >= 0.90
    assert report.mean_mrr >= 0.90
    assert report.mean_ndcg_at_5 >= 0.85
    assert report.mean_citation_precision >= 0.90
    assert report.mean_groundedness >= 0.80
    assert len(report.category_breakdowns) >= 4


def test_eval_endpoints_http():
    """Verify GET /api/v1/eval/golden and POST /api/v1/eval/benchmark HTTP endpoints."""
    client = TestClient(app)

    # 1. GET /api/v1/eval/golden
    golden_resp = client.get("/api/v1/eval/golden")
    assert golden_resp.status_code == 200
    queries = golden_resp.json()
    assert len(queries) >= 15
    assert queries[0]["query_id"] == "auth_oauth_exchange"

    # 2. POST /api/v1/eval/benchmark
    bench_resp = client.post("/api/v1/eval/benchmark")
    assert bench_resp.status_code == 200
    data = bench_resp.json()
    assert data["total_queries"] >= 15
    assert data["mean_recall_at_k"] >= 0.85
    assert data["mean_mrr"] >= 0.85
    assert data["mean_ndcg_at_5"] >= 0.80
    assert len(data["results"]) == data["total_queries"]
