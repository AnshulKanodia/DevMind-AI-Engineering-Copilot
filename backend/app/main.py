import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.trace import SpanKind

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.metrics import CONTENT_TYPE_LATEST, metrics_manager
from app.core.telemetry import (
    setup_langsmith,
    telemetry_manager,
    trace_span,
)

settings = get_settings()

# Initialize LangSmith environment on startup
setup_langsmith()

app = FastAPI(
    title=f"{settings.PROJECT_NAME} API",
    description="DevMind AI Engineering Copilot Backend API & Multi-Agent Orchestrator",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# OpenTelemetry Distributed Tracing & Prometheus HTTP Middleware
@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id")
    start_time = time.perf_counter()
    with trace_span(
        f"http.{request.method.lower()} {request.url.path}",
        attributes={
            "http.method": request.method,
            "http.url": str(request.url),
            "http.path": request.url.path,
            "devmind.component": "api_gateway",
        },
        kind=SpanKind.SERVER,
    ) as span:
        if trace_id:
            span.set_attribute("http.client_trace_id", trace_id)
        response = await call_next(request)
        duration = time.perf_counter() - start_time
        metrics_manager.record_http_request(
            request.method, request.url.path, response.status_code, duration
        )
        span.set_attribute("http.status_code", response.status_code)
        ctx = span.get_span_context() if hasattr(span, "get_span_context") else None
        if ctx and ctx.trace_id:
            response.headers["X-Trace-ID"] = format(ctx.trace_id, "032x")
        return response

# Cross-Origin Resource Sharing (CORS) Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": f"{settings.PROJECT_NAME} API",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "status": "operational",
        "description": "AI Engineering Copilot platform",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "services": {
            "api": "up",
            "telemetry": "active",
            "metrics": "active",
            "langsmith": "enabled" if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY else "disabled",
        },
    }


@app.get("/metrics", tags=["Observability"])
async def prometheus_metrics():
    """Expose Prometheus formatted metrics for scrapers (Grafana / Prometheus)."""
    return Response(
        content=metrics_manager.generate_metrics_payload(),
        media_type=CONTENT_TYPE_LATEST,
    )
