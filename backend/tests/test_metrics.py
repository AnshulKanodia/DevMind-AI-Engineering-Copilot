import pytest
from fastapi.testclient import TestClient

from app.agents.graph import devmind_workflow
from app.agents.state import create_initial_state
from app.core.metrics import MetricsManager, metrics_manager
from app.main import app


@pytest.fixture
def isolated_metrics():
    """Create an isolated MetricsManager instance with a dedicated registry."""
    from prometheus_client import CollectorRegistry
    registry = CollectorRegistry()
    return MetricsManager(registry=registry)


def test_record_http_request(isolated_metrics):
    """Verify HTTP requests are recorded into Prometheus counter and histogram."""
    isolated_metrics.record_http_request("GET", "/api/v1/repos", 200, 0.045)
    isolated_metrics.record_http_request("POST", "/api/v1/repos/clone", 201, 0.320)

    payload = isolated_metrics.generate_metrics_payload().decode("utf-8")
    assert "devmind_http_requests_total" in payload
    assert 'method="GET"' in payload
    assert 'endpoint="/api/v1/repos"' in payload
    assert 'status_code="200"' in payload
    assert "devmind_http_request_duration_seconds" in payload


def test_record_agent_node_and_intent(isolated_metrics):
    """Verify LangGraph node executions and classified intents are recorded."""
    isolated_metrics.record_agent_node("router_node", "success", 0.125)
    isolated_metrics.record_agent_node("qa_node", "success", 0.450)
    isolated_metrics.record_agent_intent("code_qa")
    isolated_metrics.record_agent_intent("security_audit")

    payload = isolated_metrics.generate_metrics_payload().decode("utf-8")
    assert 'devmind_agent_node_executions_total{node_name="router_node",status="success"}' in payload
    assert 'devmind_agent_node_executions_total{node_name="qa_node",status="success"}' in payload
    assert 'devmind_agent_intents_classified_total{intent="code_qa"}' in payload
    assert 'devmind_agent_intents_classified_total{intent="security_audit"}' in payload


def test_record_retrieval_and_citations(isolated_metrics):
    """Verify hybrid search retrieval and line citation counters."""
    isolated_metrics.record_retrieval(mode="hybrid", duration_seconds=0.085, chunk_count=5)
    isolated_metrics.record_citations([
        {"file": "auth.py", "lines": "10-25"},
        {"file": "main.py", "lines": ""},
    ])

    payload = isolated_metrics.generate_metrics_payload().decode("utf-8")
    assert 'devmind_retrieval_queries_total{mode="hybrid"}' in payload
    assert 'devmind_citations_generated_total{has_line_range="true"} 1.0' in payload
    assert 'devmind_citations_generated_total{has_line_range="false"} 1.0' in payload


def test_record_sast_findings_and_secrets(isolated_metrics):
    """Verify security audit SAST findings and secrets detections."""
    isolated_metrics.record_sast_finding("HIGH", tool="bandit")
    isolated_metrics.record_sast_finding("CRITICAL", tool="semgrep")
    isolated_metrics.record_secret_detected("aws_access_key", redacted=True)

    payload = isolated_metrics.generate_metrics_payload().decode("utf-8")
    assert 'devmind_sast_findings_total{severity="HIGH",tool="bandit"}' in payload
    assert 'devmind_sast_findings_total{severity="CRITICAL",tool="semgrep"}' in payload
    assert 'devmind_secrets_detected_total{redacted="true",secret_type="aws_access_key"}' in payload


def test_record_llm_tokens(isolated_metrics):
    """Verify LLM inference token consumption counters."""
    isolated_metrics.record_llm_tokens("gpt-4o", prompt_tokens=150, completion_tokens=50)

    payload = isolated_metrics.generate_metrics_payload().decode("utf-8")
    assert 'devmind_llm_tokens_total{model="gpt-4o",token_type="prompt"} 150.0' in payload
    assert 'devmind_llm_tokens_total{model="gpt-4o",token_type="completion"} 50.0' in payload


def test_metrics_endpoint_http():
    """Verify GET /metrics HTTP endpoint returns Prometheus formatted metrics."""
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "# HELP devmind_http_requests_total" in body
    assert "# TYPE devmind_http_requests_total counter" in body


def test_health_reports_metrics_active():
    """Verify GET /health reports metrics service as active."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["services"]["metrics"] == "active"


@pytest.mark.asyncio
async def test_agent_workflow_increments_prometheus_metrics():
    """Verify running the agent workflow increments real Prometheus counters."""
    initial_state = create_initial_state(
        repo_id="test-repo-metrics",
        user_query="Where is the database initialized?",
    )
    final_state = await devmind_workflow.execute(initial_state)
    assert final_state["current_step"] == "completed"

    payload = metrics_manager.generate_metrics_payload().decode("utf-8")
    assert "devmind_agent_node_executions_total" in payload
    assert "devmind_agent_intents_classified_total" in payload
