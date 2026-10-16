# DevMind — Video & Presentation Walkthrough Script

This script provides a structured developer demonstration of DevMind AI Engineering Copilot.

---

## Demo Overview
- **Target Audience**: Engineering Leads, Developers, Security Engineers, and Technical Interviewers.
- **Duration**: ~4–5 Minutes.
- **Key Message**: DevMind is not just another chatbot; it is a grounded, security-hardened repository intelligence engine that cites exact AST line numbers, detects vulnerabilities, and guides software teams without hallucinations.

---

## Scene 1: Repository Linking & Natural Conversational Greeting
**Action**:
1. Open [https://devmind-copilot.vercel.app](https://devmind-copilot.vercel.app).
2. Enter repository URL: `https://github.com/AnshulKanodia/Personal-Finance-Management`.
3. In the chat prompt, type: `hey`.

**Spoken Narration**:
> *"Notice how DevMind connects directly to the repository and greets us conversationally with verified metadata and suggested technical queries, rather than immediately dumping unprompted architecture."*

---

## Scene 2: Grounded Q&A with Exact Line Citations
**Action**:
1. In the chat, ask: `How is the PIN vault security implemented?`
2. Point out the live Agent Thought Timeline:
   - **Router Agent**: Classifies query as `code_qa`.
   - **Retriever Agent**: Executes hybrid BM25 + dense search across AST chunks.
   - **Synthesizer Agent**: Streams the response token-by-token.
3. Click on the citation tag `[auth.py:45-88]` or `[README.md:162-240]`.

**Spoken Narration**:
> *"Unlike standard LLMs that generate plausible-sounding answers, DevMind grounds every statement directly on retrieved AST line ranges. Clicking any citation opens the exact source code snippet in the side drawer."*

---

## Scene 3: Environment Setup & Zero-Config Detection
**Action**:
1. For `Personal-Finance-Management`, ask: `what env do i need?`
   - DevMind parses `.env.example` directly from the repository, outputting a structured Markdown table of required variables (`MONGODB_URI`, `APP_PIN`, `SESSION_SECRET`).
2. Switch repo to `https://github.com/AnshulKanodia/Anshul-Kanodia-Portfolio` and ask: `what env do i need?`
   - DevMind autonomously inspects the static HTML5 architecture and clarifies: *"No environment variables required! Built with lightweight vanilla web standards."*

**Spoken Narration**:
> *"DevMind dynamically adapts to the architecture of any connected repository—whether it's a full-stack Next.js application requiring MongoDB secrets or a client-side static portal with zero runtime dependencies."*

---

## Scene 4: Execution & Hosting Intelligence
**Action**:
1. Ask: `where it is hosted?`
   - DevMind discovers the live production URL `https://anshulkanodia.me/` and identifies the Vercel Edge deployment target.
2. Ask: `how do i run it?`
   - DevMind delivers complete, non-empty, executable setup instructions from the project documentation.

---

## Scene 5: Production CI/CD & RAG Evaluation Gates
**Action**:
1. Open GitHub Actions tab.
2. Show the monorepo CI workflow ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)):
   - Backend `pytest` suite (199 passing tests).
   - Frontend unit test suite (16 passing tests).
   - RAG Golden Evaluation Gate verifying Recall@K $\ge 88\%$ and Mean Reciprocal Rank (MRR).
   - Multi-stage non-root container build validation.

**Closing Narration**:
> *"From syntax-aware AST parsing to strict citation guarantees, non-root Kubernetes hardening, and automated RAG evaluation gates, DevMind delivers an enterprise-grade AI Engineering Copilot built for real production codebases."*
