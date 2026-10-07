# DevMind — AI Engineering Copilot

DevMind is an intelligent AI assistant platform designed to help developers navigate, understand, test, and improve codebases using LLMs and specialized agents.

## Architecture

- **Frontend**: Next.js 14+ (App Router, TypeScript, Tailwind CSS, Lucide icons)
- **Backend API**: Python FastAPI (async routes, Server-Sent Events for streaming)
- **Orchestration**: LangGraph stateful multi-agent workflow
- **Vector Search**: MongoDB Atlas Vector Search (HNSW + hybrid BM25 retrieval)
- **Static Analysis (SAST)**: Bandit, ESLint, Semgrep
- **Evaluation**: RAG ground-truth evaluation benchmark suite

## Directory Layout

```text
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph multi-agent orchestrator & workers
│   │   ├── api/             # FastAPI routers and route handlers
│   │   ├── core/            # Config, security, database connectors
│   │   ├── schemas/         # Pydantic models and request/response contracts
│   │   ├── services/        # Git cloner, AST chunker, SAST runner, LLM services
│   │   └── main.py          # FastAPI application entrypoint
│   ├── pyproject.toml       # Python package configuration
│   └── requirements.txt     # Python backend dependencies
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router (pages and layouts)
│   │   └── lib/             # Shared frontend utilities
│   ├── package.json         # Frontend dependencies and build scripts
│   ├── tailwind.config.ts   # Tailwind CSS styling configuration
│   └── tsconfig.json        # TypeScript configuration
├── package.json             # Root monorepo workspace configuration
├── IMPLEMENTATION_PLAN.md   # 10-phase roadmap with commit-by-commit specs
└── README.md                # Project documentation
```

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

FastAPI OpenAPI documentation will be accessible at: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Next.js web interface will be accessible at: `http://localhost:3000`
