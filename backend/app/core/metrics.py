from typing import Any, Dict, List, Optional
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ---------------------------------------------------------------------------
# DevMind Prometheus Metrics Registry & Definitions
# ---------------------------------------------------------------------------

class MetricsManager:
    """Manages Prometheus metrics registration, recording, and exposition."""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()

        # HTTP Traffic Metrics
        self.http_requests_total = Counter(
            "devmind_http_requests_total",
            "Total count of HTTP requests processed by API gateway",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )
        self.http_request_duration_seconds = Histogram(
            "devmind_http_request_duration_seconds",
            "HTTP request latency in seconds",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry,
        )

        # LangGraph Multi-Agent Orchestration Metrics
        self.agent_node_executions_total = Counter(
            "devmind_agent_node_executions_total",
            "Total count of LangGraph node executions",
            ["node_name", "status"],
            registry=self.registry,
        )
        self.agent_node_duration_seconds = Histogram(
            "devmind_agent_node_duration_seconds",
            "Execution latency per LangGraph agent node in seconds",
            ["node_name"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 30.0],
            registry=self.registry,
        )
        self.agent_intents_classified_total = Counter(
            "devmind_agent_intents_classified_total",
            "Distribution of queries classified by the Intent Router Agent",
            ["intent"],
            registry=self.registry,
        )
        self.agent_active_sessions = Gauge(
            "devmind_agent_active_sessions",
            "Number of concurrently active agent sessions",
            ["mode"],
            registry=self.registry,
        )

        # Code Retrieval & Vector Search Metrics
        self.retrieval_queries_total = Counter(
            "devmind_retrieval_queries_total",
            "Total code search retrieval queries executed",
            ["mode"],
            registry=self.registry,
        )
        self.retrieval_duration_seconds = Histogram(
            "devmind_retrieval_duration_seconds",
            "Hybrid BM25 + dense vector search latency in seconds",
            ["mode"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry,
        )
        self.retrieved_chunks_count = Histogram(
            "devmind_retrieved_chunks_count",
            "Number of code chunks retrieved per query",
            ["mode"],
            buckets=[1, 3, 5, 8, 10, 15, 20, 50],
            registry=self.registry,
        )
        self.citations_generated_total = Counter(
            "devmind_citations_generated_total",
            "Total AST source citations generated with exact line ranges",
            ["has_line_range"],
            registry=self.registry,
        )

        # Static Analysis (SAST) & Security Metrics
        self.sast_scans_total = Counter(
            "devmind_sast_scans_total",
            "Total static analysis scans performed",
            ["scan_type"],
            registry=self.registry,
        )
        self.sast_findings_total = Counter(
            "devmind_sast_findings_total",
            "Total security & defect findings detected by SAST rules",
            ["severity", "tool"],
            registry=self.registry,
        )
        self.secrets_detected_total = Counter(
            "devmind_secrets_detected_total",
            "Total credentials detected during repository sanitization",
            ["secret_type", "redacted"],
            registry=self.registry,
        )

        # LLM & Token Consumption Metrics
        self.llm_tokens_total = Counter(
            "devmind_llm_tokens_total",
            "Total LLM tokens consumed across reasoning and synthesis",
            ["model", "token_type"],
            registry=self.registry,
        )
        self.embedding_tokens_total = Counter(
            "devmind_embedding_tokens_total",
            "Total tokens processed for vector embedding generation",
            ["model"],
            registry=self.registry,
        )

    # -----------------------------------------------------------------------
    # Recording Helpers
    # -----------------------------------------------------------------------

    def record_http_request(
        self, method: str, endpoint: str, status_code: int, duration_seconds: float
    ) -> None:
        """Record HTTP endpoint latency and status code counter."""
        norm_endpoint = endpoint.split("?")[0]
        self.http_requests_total.labels(
            method=method, endpoint=norm_endpoint, status_code=str(status_code)
        ).inc()
        self.http_request_duration_seconds.labels(
            method=method, endpoint=norm_endpoint
        ).observe(duration_seconds)

    def record_agent_node(
        self, node_name: str, status: str, duration_seconds: float
    ) -> None:
        """Record LangGraph node execution duration and outcome."""
        self.agent_node_executions_total.labels(
            node_name=node_name, status=status
        ).inc()
        self.agent_node_duration_seconds.labels(node_name=node_name).observe(
            duration_seconds
        )

    def record_agent_intent(self, intent: str) -> None:
        """Increment count for classified developer intent."""
        self.agent_intents_classified_total.labels(intent=intent).inc()

    def record_retrieval(
        self, mode: str, duration_seconds: float, chunk_count: int
    ) -> None:
        """Record hybrid retrieval duration and number of relevant chunks surfaced."""
        self.retrieval_queries_total.labels(mode=mode).inc()
        self.retrieval_duration_seconds.labels(mode=mode).observe(duration_seconds)
        self.retrieved_chunks_count.labels(mode=mode).observe(chunk_count)

    def record_citations(self, citations: List[Any]) -> None:
        """Record count of line-anchored citations emitted."""
        for c in citations:
            line_val = getattr(c, "lines", "") if hasattr(c, "lines") else (c.get("lines") if isinstance(c, dict) else "")
            has_range = "true" if line_val else "false"
            self.citations_generated_total.labels(has_line_range=has_range).inc()

    def record_sast_finding(self, severity: str, tool: str = "bandit") -> None:
        """Record a security finding categorized by severity and analyzer tool."""
        self.sast_findings_total.labels(
            severity=severity.upper(), tool=tool.lower()
        ).inc()

    def record_secret_detected(
        self, secret_type: str, redacted: bool = True
    ) -> None:
        """Record detected credential during secret scanning."""
        self.secrets_detected_total.labels(
            secret_type=secret_type, redacted=str(redacted).lower()
        ).inc()

    def record_llm_tokens(
        self, model: str, prompt_tokens: int = 0, completion_tokens: int = 0
    ) -> None:
        """Record prompt and completion tokens consumed by inference."""
        if prompt_tokens > 0:
            self.llm_tokens_total.labels(model=model, token_type="prompt").inc(
                prompt_tokens
            )
        if completion_tokens > 0:
            self.llm_tokens_total.labels(
                model=model, token_type="completion"
            ).inc(completion_tokens)

    def generate_metrics_payload(self) -> bytes:
        """Format and return current Prometheus exposition text."""
        return generate_latest(self.registry)


# Global Metrics Singleton
metrics_manager = MetricsManager()
