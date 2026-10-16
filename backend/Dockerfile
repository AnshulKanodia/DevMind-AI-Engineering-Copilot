# ===========================================================================
# Stage 1: Build virtual environment and wheels
# ===========================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Install compilation build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create isolated Python virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ===========================================================================
# Stage 2: Hardened Runtime Container
# ===========================================================================
FROM python:3.11-slim AS runner

WORKDIR /app

# Install minimal runtime system utilities (git for cloner, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Security Hardening: Create non-root unprivileged user and group
RUN groupadd --system --gid 10001 appgroup && \
    useradd --system --uid 10001 --gid appgroup --no-create-home --shell /usr/sbin/nologin appuser

# Set up ephemeral sandboxed directory with strict ownership
RUN mkdir -p /tmp/devmind-sandboxes && \
    chown -R appuser:appgroup /tmp/devmind-sandboxes && \
    chmod 700 /tmp/devmind-sandboxes

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SANDBOX_TEMP_DIR=/tmp/devmind-sandboxes

# Copy application source code with non-root ownership
COPY --chown=appuser:appgroup app /app/app
COPY --chown=appuser:appgroup pyproject.toml /app/

# Switch to unprivileged security context
USER appuser

EXPOSE 8000

# Docker healthcheck pinging FastAPI /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Launch ASGI application server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
