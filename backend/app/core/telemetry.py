from contextlib import asynccontextmanager, contextmanager
from functools import wraps
import inspect
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Union

from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Span, SpanKind, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from app.core.config import get_settings

logger = logging.getLogger("devmind.telemetry")


# ---------------------------------------------------------------------------
# LangSmith Configuration & Integration
# ---------------------------------------------------------------------------

def setup_langsmith() -> Dict[str, Any]:
    """Configure LangSmith / LangChain distributed tracing environment variables."""
    settings = get_settings()
    tracing_enabled = bool(settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY)

    if tracing_enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        logger.info(
            f"LangSmith distributed tracing enabled for project '{settings.LANGCHAIN_PROJECT}'"
        )
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"

    return {
        "enabled": tracing_enabled,
        "endpoint": settings.LANGCHAIN_ENDPOINT,
        "project": settings.LANGCHAIN_PROJECT,
    }


# ---------------------------------------------------------------------------
# OpenTelemetry Tracer Provider & In-Memory Exporter
# ---------------------------------------------------------------------------

class TelemetryManager:
    """Manages OpenTelemetry distributed tracing, context propagation, and in-memory span harvesting."""

    def __init__(self):
        settings = get_settings()
        self.resource = Resource.create(
            {
                "service.name": "devmind-copilot",
                "service.version": "1.0.0",
                "deployment.environment": settings.ENVIRONMENT,
            }
        )
        self.tracer_provider = TracerProvider(resource=self.resource)
        self.in_memory_exporter = InMemorySpanExporter()
        self.span_processor = SimpleSpanProcessor(self.in_memory_exporter)
        self.tracer_provider.add_span_processor(self.span_processor)

        # Set tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        self.tracer = trace.get_tracer("devmind.telemetry", "1.0.0")
        self.propagator = TraceContextTextMapPropagator()

    def get_tracer(self) -> trace.Tracer:
        """Return the active OpenTelemetry tracer."""
        return self.tracer

    def get_recorded_spans(self) -> List[Dict[str, Any]]:
        """Return all recorded spans in the in-memory buffer formatted as serializable dictionaries."""
        raw_spans = self.in_memory_exporter.get_finished_spans()
        result: List[Dict[str, Any]] = []
        for s in raw_spans:
            duration_ms = 0.0
            if s.end_time and s.start_time:
                duration_ms = round((s.end_time - s.start_time) / 1_000_000, 2)

            trace_id = format(s.context.trace_id, "032x") if s.context else ""
            span_id = format(s.context.span_id, "016x") if s.context else ""
            parent_span_id = (
                format(s.parent.span_id, "016x") if s.parent and s.parent.span_id else None
            )

            result.append(
                {
                    "name": s.name,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id,
                    "status_code": s.status.status_code.name if s.status else "UNSET",
                    "status_description": s.status.description if s.status else None,
                    "attributes": dict(s.attributes) if s.attributes else {},
                    "duration_ms": duration_ms,
                    "events": [
                        {"name": e.name, "timestamp": e.timestamp, "attributes": dict(e.attributes)}
                        for e in s.events
                    ],
                }
            )
        return result

    def clear_recorded_spans(self) -> None:
        """Clear all finished spans from the in-memory buffer."""
        self.in_memory_exporter.clear()

    def inject_trace_context(self, carrier: Dict[str, str]) -> Dict[str, str]:
        """Inject W3C traceparent and tracestate into a carrier dictionary."""
        self.propagator.inject(carrier)
        return carrier

    def extract_trace_context(self, carrier: Dict[str, str]):
        """Extract W3C trace context from carrier headers."""
        return self.propagator.extract(carrier)


# Global Telemetry Singleton
telemetry_manager = TelemetryManager()
tracer = telemetry_manager.get_tracer()


# ---------------------------------------------------------------------------
# Span Context Manager & Decorator
# ---------------------------------------------------------------------------

class SpanContext:
    """Universal synchronous & asynchronous span context manager for OpenTelemetry."""

    def __init__(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        kind: SpanKind = SpanKind.INTERNAL,
    ):
        self.name = name
        self.attributes = attributes or {}
        self.kind = kind
        self.span: Optional[Span] = None
        self._token = None
        self._start_time: float = 0.0

    def __enter__(self) -> Span:
        self._start_time = time.perf_counter()
        self.span = tracer.start_span(self.name, kind=self.kind)
        for k, v in self.attributes.items():
            if v is not None:
                self.span.set_attribute(k, v)
        self._scope = trace.use_span(self.span, end_on_exit=False)
        self._scope.__enter__()
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if hasattr(self, "_scope") and self._scope:
                self._scope.__exit__(exc_type, exc_val, exc_tb)
            if self.span:
                if exc_type is not None:
                    self.span.record_exception(exc_val)
                    self.span.set_status(StatusCode.ERROR, str(exc_val))
                else:
                    self.span.set_status(StatusCode.OK)
                self.span.end()
        finally:
            pass
        return False

    async def __aenter__(self) -> Span:
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> SpanContext:
    """Create a synchronous or asynchronous trace span context manager."""
    return SpanContext(name, attributes=attributes, kind=kind)


def traced(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Decorator to trace synchronous or asynchronous functions with OpenTelemetry."""
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                attrs = dict(attributes or {})
                with trace_span(span_name, attributes=attrs):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                attrs = dict(attributes or {})
                with trace_span(span_name, attributes=attrs):
                    return func(*args, **kwargs)
            return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Specialized DevMind Domain Tracing Helpers
# ---------------------------------------------------------------------------

def trace_agent_node(
    node_name: str,
    repo_id: Optional[str] = None,
    intent: Optional[str] = None,
    step: Optional[str] = None,
) -> SpanContext:
    """Trace a LangGraph multi-agent execution node."""
    attrs: Dict[str, Any] = {
        "devmind.component": "agent_graph",
        "agent.node": node_name,
    }
    if repo_id:
        attrs["devmind.repo_id"] = repo_id
    if intent:
        attrs["agent.intent"] = intent
    if step:
        attrs["agent.step"] = step

    return trace_span(f"devmind.agent.{node_name}", attributes=attrs)


def trace_retrieval(
    query: str,
    repo_id: str,
    top_k: int = 5,
    mode: str = "hybrid",
) -> SpanContext:
    """Trace code search retrieval (BM25 lexical + dense vector k-NN)."""
    attrs: Dict[str, Any] = {
        "devmind.component": "retriever",
        "retrieval.query": query[:128],
        "retrieval.repo_id": repo_id,
        "retrieval.top_k": top_k,
        "retrieval.mode": mode,
    }
    return trace_span("devmind.retrieval.search", attributes=attrs)


def trace_llm_generation(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> SpanContext:
    """Trace LLM inference calls and token consumption."""
    attrs: Dict[str, Any] = {
        "devmind.component": "llm_client",
        "llm.model": model,
        "llm.prompt_tokens": prompt_tokens,
        "llm.completion_tokens": completion_tokens,
        "llm.total_tokens": prompt_tokens + completion_tokens,
    }
    return trace_span("devmind.llm.generate", attributes=attrs)


def trace_sast_scan(repo_id: str, scan_type: str) -> SpanContext:
    """Trace static analysis (Bandit, Semgrep, ESLint) security execution."""
    attrs: Dict[str, Any] = {
        "devmind.component": "sast_pipeline",
        "sast.repo_id": repo_id,
        "sast.scan_type": scan_type,
    }
    return trace_span(f"devmind.sast.{scan_type}", attributes=attrs)


# ---------------------------------------------------------------------------
# LangChain / LangGraph Callback Handler
# ---------------------------------------------------------------------------

class DevMindTelemetryCallbackHandler:
    """Callback handler compatible with LangChain / LangGraph components for distributed telemetry."""

    def __init__(self, repo_id: Optional[str] = None):
        self.repo_id = repo_id
        self._active_spans: Dict[str, Span] = {}

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        name = serialized.get("name", "langgraph_chain") if serialized else "langgraph_chain"
        span = tracer.start_span(
            f"devmind.chain.{name}",
            kind=SpanKind.INTERNAL,
        )
        if self.repo_id:
            span.set_attribute("devmind.repo_id", self.repo_id)
        span.set_attribute("devmind.component", "langchain_orchestration")
        run_id = str(kwargs.get("run_id", name))
        self._active_spans[run_id] = span

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", "langgraph_chain"))
        span = self._active_spans.pop(run_id, None)
        if span:
            span.set_status(StatusCode.OK)
            span.end()

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", "langgraph_chain"))
        span = self._active_spans.pop(run_id, None)
        if span:
            span.record_exception(error)
            span.set_status(StatusCode.ERROR, str(error))
            span.end()

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "tool") if serialized else "tool"
        span = tracer.start_span(f"devmind.tool.{tool_name}")
        span.set_attribute("tool.name", tool_name)
        run_id = str(kwargs.get("run_id", tool_name))
        self._active_spans[run_id] = span

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", "tool"))
        span = self._active_spans.pop(run_id, None)
        if span:
            span.set_status(StatusCode.OK)
            span.end()

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", "tool"))
        span = self._active_spans.pop(run_id, None)
        if span:
            span.record_exception(error)
            span.set_status(StatusCode.ERROR, str(error))
            span.end()
