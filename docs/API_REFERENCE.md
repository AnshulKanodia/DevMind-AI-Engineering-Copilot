# DevMind — REST API & Server-Sent Events (SSE) Reference

This document provides the complete API specification for DevMind AI Engineering Copilot.

---

## Base URLs

- **Production (Web & API)**: `https://devmind-copilot.vercel.app`
- **Internal Cluster API**: `http://devmind-backend.devmind.svc.cluster.local:8000`
- **Local Development**: `http://localhost:8000` (Backend) / `http://localhost:3000` (Frontend)

---

## 1. System & Health Endpoints

### `GET /health`
Returns live service health status, telemetry state, and database connectivity.

**Response `200 OK`**:
```json
{
  "status": "healthy",
  "environment": "production",
  "services": {
    "api": "up",
    "telemetry": "active",
    "metrics": "active",
    "langsmith": "enabled"
  }
}
```

### `GET /metrics`
Exposes Prometheus-formatted operational metrics (request duration, vector retrieval latency, active SSE streams, token consumption).

---

## 2. Multi-Agent Chat Streaming

### `POST /api/v1/agents/stream`
Initiates a real-time Server-Sent Events (SSE) stream orchestrating the multi-agent reasoning chain.

**Request Body**:
```json
{
  "repo_id": "AnshulKanodia/Personal-Finance-Management",
  "query": "How is authentication handled?"
}
```

**SSE Event Protocol**:

| Event Type | Payload Schema | Description |
| :--- | :--- | :--- |
| `node_start` | `{"node": "router" \| "retriever" \| "synthesizer"}` | Emitted when a LangGraph agent node begins execution. |
| `intent_classified` | `{"intent": "...", "confidence": 0.98, "message": "..."}` | Router classification output. |
| `retrieval_complete` | `{"chunk_count": 3, "strategy": "hybrid_ast_bm25_dense"}` | Grounded retrieval summary. |
| `token` | `{"token": "..."}` | Incremental markdown response token. |
| `citations` | `{"citations": ["auth.py:45-88", "README.md:162-240"]}` | Verified source file and line citations. |
| `done` | `{"status": "completed"}` | Stream termination frame. |

---

## 3. Repository Onboarding & Profiling

### `POST /api/v1/repos/onboard`
Triggers sandboxed cloning, AST parsing, secrets sanitization, and vector indexing.

**Request Body**:
```json
{
  "repo_url": "https://github.com/owner/repository",
  "branch": "main"
}
```

**Response `202 Accepted`**:
```json
{
  "repo_id": "owner/repository",
  "status": "indexing",
  "total_files": 42,
  "estimated_chunks": 180
}
```

---

## 4. Security Auditing & SAST

### `POST /api/v1/security/scan`
Executes hybrid static analysis (Bandit, ESLint, OWASP rules) and correlates findings with LLM reasoning.

**Request Body**:
```json
{
  "repo_id": "owner/repository",
  "severity_threshold": "MEDIUM"
}
```

**Response `200 OK`**:
```json
{
  "vulnerabilities": [
    {
      "id": "SEC-001",
      "severity": "HIGH",
      "cwe": "CWE-89",
      "file": "app/db.py",
      "lines": "34-36",
      "description": "Potential SQL injection in dynamic query string construction",
      "remediation": "Use parameterized ORM queries via SQLAlchemy or Mongoose"
    }
  ],
  "total_scanned_files": 54,
  "false_positive_reduction_rate": 0.85
}
```

---

## 5. Rate Limiting & Error Codes

All endpoints enforce a sliding-window rate limit (default: 60 req/min per IP/token).

| Header | Description |
| :--- | :--- |
| `X-RateLimit-Limit` | Maximum requests permitted in the window. |
| `X-RateLimit-Remaining` | Remaining requests available. |
| `X-Trace-ID` | Distributed OpenTelemetry trace identifier. |
| `Retry-After` | Seconds to wait before retrying when rate-limited. |

**Standard HTTP Status Codes**:
- `200 OK`: Request succeeded.
- `400 Bad Request`: Invalid JSON body or unresolvable repository format.
- `401 Unauthorized`: Missing or invalid bearer token.
- `429 Too Many Requests`: Rate limit threshold exceeded.
- `500 Internal Server Error`: Serverless or backend orchestration failure.
