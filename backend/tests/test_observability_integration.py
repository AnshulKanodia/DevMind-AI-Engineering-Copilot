import pytest
from fastapi.testclient import TestClient

from app.core.guardrails import token_guardrail
from app.core.metrics import metrics_manager
from app.core.rate_limiter import rate_limiter
from app.core.telemetry import telemetry_manager
from app.main import app


@pytest.fixture(autouse=True)
def clean_observability_state():
    """Clean telemetry spans, rate limiter buckets, and test repo usage accounts."""
    telemetry_manager.clear_recorded_spans()
    rate_limiter.reset()
    token_guardrail.reset_usage("test-obs-repo")
    yield
    telemetry_manager.clear_recorded_spans()
    rate_limiter.reset()
    token_guardrail.reset_usage("test-obs-repo")


def test_end_to_end_observability_pipeline():
    """Verify end-to-end integration across HTTP, OpenTelemetry spans, Prometheus metrics, and Guardrails."""
    client = TestClient(app)

    # 1. Execute an agent chat request through the HTTP API
    payload = {
        "repo_id": "test-obs-repo",
        "query": "How are database migrations managed in this codebase?",
        "messages": [],
    }
    response = client.post("/api/v1/agents/chat", json=payload)
    assert response.status_code == 200

    # 2. Verify distributed tracing headers
    assert "X-Trace-ID" in response.headers
    trace_id = response.headers["X-Trace-ID"]
    assert len(trace_id) == 32

    # 3. Verify rate limiting headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers

    # 4. Verify OpenTelemetry spans recorded
    spans = telemetry_manager.get_recorded_spans()
    assert len(spans) >= 3

    span_names = [s["name"] for s in spans]
    assert "http.post /api/v1/agents/chat" in span_names
    assert "devmind.agent.workflow" in span_names
    assert "devmind.agent.router_node" in span_names

    # Check span attributes
    http_span = next(s for s in spans if s["name"] == "http.post /api/v1/agents/chat")
    assert http_span["attributes"]["http.status_code"] == 200
    assert http_span["attributes"]["devmind.component"] == "api_gateway"

    # 5. Scrape and verify Prometheus /metrics endpoint
    metrics_resp = client.get("/metrics")
    assert metrics_resp.status_code == 200
    metrics_text = metrics_resp.text

    assert "devmind_http_requests_total" in metrics_text
    assert 'endpoint="/api/v1/agents/chat"' in metrics_text
    assert "devmind_agent_node_executions_total" in metrics_text
    assert 'node_name="router_node"' in metrics_text
    assert "devmind_llm_tokens_total" in metrics_text

    # 6. Verify Token Guardrail registered consumption
    usage_resp = client.get("/api/v1/guardrails/usage/test-obs-repo")
    assert usage_resp.status_code == 200
    usage_data = usage_resp.json()

    assert usage_data["repo_id"] == "test-obs-repo"
    assert usage_data["total_tokens"] > 0
    assert usage_data["prompt_tokens"] > 0
    assert usage_data["completion_tokens"] > 0
    assert usage_data["requests_count"] == 1
    assert usage_data["remaining_tokens"] > 0
    assert usage_data["degradation_active"] is False


def test_graceful_degradation_when_token_budget_approaching_cap():
    """Verify that when a repository token budget approaches >80%, degradation flag is surfaced."""
    client = TestClient(app)

    # Pre-load usage to 85% of budget
    account = token_guardrail._get_or_create_account("test-obs-repo")
    budget = account["max_tokens_budget"]
    account["total_tokens"] = int(budget * 0.85)
    account["prompt_tokens"] = int(budget * 0.50)
    account["completion_tokens"] = int(budget * 0.35)

    # Execute workflow and verify degradation_active is passed to response
    payload = {
        "repo_id": "test-obs-repo",
        "query": "Explain authentication mechanisms",
    }
    response = client.post("/api/v1/agents/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"].get("degradation_active") is True
