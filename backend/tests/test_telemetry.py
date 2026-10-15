import os
import pytest
from fastapi.testclient import TestClient

from app.agents.graph import devmind_workflow
from app.agents.state import create_initial_state
from app.core.config import get_settings
from app.core.telemetry import (
    DevMindTelemetryCallbackHandler,
    setup_langsmith,
    telemetry_manager,
    trace_agent_node,
    trace_llm_generation,
    trace_retrieval,
    trace_sast_scan,
    trace_span,
    traced,
)
from app.main import app


@pytest.fixture(autouse=True)
def clean_spans():
    """Ensure in-memory span buffer is clean before and after each test."""
    telemetry_manager.clear_recorded_spans()
    yield
    telemetry_manager.clear_recorded_spans()


def test_langsmith_setup_disabled_when_unconfigured(monkeypatch):
    """Verify that LangSmith tracing is safely disabled when API key is missing."""
    settings = get_settings()
    monkeypatch.setattr(settings, "LANGCHAIN_TRACING_V2", False)
    monkeypatch.setattr(settings, "LANGCHAIN_API_KEY", "")

    result = setup_langsmith()
    assert result["enabled"] is False
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"


def test_langsmith_setup_enabled(monkeypatch):
    """Verify that LangSmith tracing populates environment variables when configured."""
    settings = get_settings()
    monkeypatch.setattr(settings, "LANGCHAIN_TRACING_V2", True)
    monkeypatch.setattr(settings, "LANGCHAIN_API_KEY", "lsv2_pt_test_key_12345")
    monkeypatch.setattr(settings, "LANGCHAIN_PROJECT", "devmind-test-suite")

    result = setup_langsmith()
    assert result["enabled"] is True
    assert result["project"] == "devmind-test-suite"
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
    assert os.environ.get("LANGCHAIN_PROJECT") == "devmind-test-suite"


def test_trace_span_sync_context():
    """Verify that synchronous trace_span records span metadata and attributes."""
    with trace_span("test.sync_operation", attributes={"custom.metric": 42}) as span:
        span.set_attribute("runtime.tag", "passed")

    spans = telemetry_manager.get_recorded_spans()
    assert len(spans) == 1
    recorded = spans[0]
    assert recorded["name"] == "test.sync_operation"
    assert recorded["status_code"] == "OK"
    assert recorded["attributes"]["custom.metric"] == 42
    assert recorded["attributes"]["runtime.tag"] == "passed"
    assert recorded["trace_id"] != ""
    assert recorded["span_id"] != ""


@pytest.mark.asyncio
async def test_trace_span_async_context():
    """Verify that asynchronous trace_span records span metadata."""
    async with trace_span("test.async_operation", attributes={"is_async": True}) as span:
        span.set_attribute("async_detail", "completed")

    spans = telemetry_manager.get_recorded_spans()
    assert len(spans) == 1
    assert spans[0]["name"] == "test.async_operation"
    assert spans[0]["attributes"]["is_async"] is True
    assert spans[0]["status_code"] == "OK"


def test_trace_span_records_exception():
    """Verify that exceptions inside a trace span are recorded and mark the span as ERROR."""
    with pytest.raises(ValueError, match="simulated failure"):
        with trace_span("test.error_operation"):
            raise ValueError("simulated failure")

    spans = telemetry_manager.get_recorded_spans()
    assert len(spans) == 1
    recorded = spans[0]
    assert recorded["status_code"] == "ERROR"
    assert "simulated failure" in recorded["status_description"]


def test_traced_decorator_sync_and_async():
    """Verify @traced decorator records spans for both sync and async methods."""
    @traced("test.decorated_sync", attributes={"scope": "unit_test"})
    def sample_sync(x: int) -> int:
        return x * 2

    assert sample_sync(5) == 10

    spans = telemetry_manager.get_recorded_spans()
    assert len(spans) == 1
    assert spans[0]["name"] == "test.decorated_sync"
    assert spans[0]["attributes"]["scope"] == "unit_test"


@pytest.mark.asyncio
async def test_traced_decorator_async():
    """Verify @traced decorator on async coroutines."""
    @traced("test.decorated_async", attributes={"protocol": "sse"})
    async def sample_async(msg: str) -> str:
        return f"echo: {msg}"

    res = await sample_async("hello")
    assert res == "echo: hello"

    spans = telemetry_manager.get_recorded_spans()
    assert len(spans) == 1
    assert spans[0]["name"] == "test.decorated_async"
    assert spans[0]["attributes"]["protocol"] == "sse"


def test_domain_tracing_helpers():
    """Verify specialized domain tracing helpers populate canonical DevMind telemetry attributes."""
    with trace_agent_node("qa_node", repo_id="demo-repo", intent="code_qa"):
        pass

    with trace_retrieval(query="find auth handler", repo_id="demo-repo", top_k=7, mode="hybrid"):
        pass

    with trace_llm_generation(model="gpt-4o", prompt_tokens=250, completion_tokens=100):
        pass

    with trace_sast_scan(repo_id="demo-repo", scan_type="bandit"):
        pass

    spans = telemetry_manager.get_recorded_spans()
    assert len(spans) == 4

    span_names = [s["name"] for s in spans]
    assert "devmind.agent.qa_node" in span_names
    assert "devmind.retrieval.search" in span_names
    assert "devmind.llm.generate" in span_names
    assert "devmind.sast.bandit" in span_names

    llm_span = next(s for s in spans if s["name"] == "devmind.llm.generate")
    assert llm_span["attributes"]["llm.total_tokens"] == 350


def test_context_propagation():
    """Verify W3C traceparent carrier injection and extraction."""
    carrier = {}
    with trace_span("test.parent"):
        telemetry_manager.inject_trace_context(carrier)

    assert "traceparent" in carrier
    assert carrier["traceparent"].startswith("00-")

    extracted_ctx = telemetry_manager.extract_trace_context(carrier)
    assert extracted_ctx is not None


def test_http_middleware_records_server_span():
    """Verify FastAPI telemetry middleware creates SERVER spans with status code and X-Trace-ID header."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Trace-ID" in response.headers
    data = response.json()
    assert data["services"]["telemetry"] == "active"

    spans = telemetry_manager.get_recorded_spans()
    assert len(spans) >= 1
    http_span = next((s for s in spans if s["name"] == "http.get /health"), None)
    assert http_span is not None
    assert http_span["attributes"]["http.status_code"] == 200
    assert http_span["attributes"]["devmind.component"] == "api_gateway"


@pytest.mark.asyncio
async def test_agent_workflow_traces_nodes():
    """Verify running the multi-agent workflow records parent workflow and agent node spans."""
    initial_state = create_initial_state(
        repo_id="test-repo-telemetry",
        user_query="How does authentication work?",
    )
    final_state = await devmind_workflow.execute(initial_state)
    assert final_state["current_step"] == "completed"

    spans = telemetry_manager.get_recorded_spans()
    span_names = [s["name"] for s in spans]
    assert "devmind.agent.workflow" in span_names
    assert "devmind.agent.router_node" in span_names
