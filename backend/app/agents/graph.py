import logging
import time
from typing import Any, Callable, Dict, List, Optional

import re
from app.agents.state import AgentIntent, AgentState
from app.schemas.bug import BugHuntRequest
from app.schemas.doc_gen import DocGenRequest
from app.schemas.pr_review import PRReviewRequest
from app.schemas.security import SecurityAuditRequest
from app.schemas.test_gen import TestGenRequest
from app.services.bug_agent import bug_agent_service
from app.services.doc_agent import doc_agent_service
from app.services.pr_review_agent import pr_review_agent_service
from app.services.qa_agent import qa_agent_service
from app.services.router_agent import router_agent_service
from app.services.security_agent import security_agent_service
from app.services.test_agent import test_agent_service
from app.core.metrics import metrics_manager
from app.core.telemetry import trace_agent_node, trace_span

logger = logging.getLogger("devmind.agents.graph")


# ---------------------------------------------------------------------------
# Base Agent Nodes (Base Implementations for Multi-Agent Orchestration)
# ---------------------------------------------------------------------------

async def router_node(state: AgentState) -> AgentState:
    """Analyze user query and determine appropriate specialized sub-agent."""
    query = state.get("user_query", "")
    state["iteration_count"] = state.get("iteration_count", 0) + 1
    state["current_step"] = "routing"

    # Invoke LLM Router Agent
    result = await router_agent_service.classify_query(query)

    state["intent"] = result.intent.value
    if "metadata" not in state or state["metadata"] is None:
        state["metadata"] = {}

    state["metadata"]["router_confidence"] = result.confidence
    state["metadata"]["router_reasoning"] = result.reasoning
    state["metadata"]["target_subagent"] = result.target_subagent
    state["metadata"]["suggested_search_queries"] = result.suggested_search_queries
    return state


async def qa_node(state: AgentState) -> AgentState:
    """Code Q&A node: grounded retrieval and answer synthesis."""
    state["current_step"] = "executing_qa"
    state["next_node"] = "format_node"

    repo_id = state.get("repo_id", "")
    query = state.get("user_query", "")

    # Retrieve and synthesize grounded answer with line citations
    qa_resp = await qa_agent_service.answer_query(repo_id=repo_id, query=query)

    state["final_response"] = qa_resp.answer
    state["citations"] = qa_resp.citations
    state["retrieved_chunks"] = [c.model_dump() for c in qa_resp.retrieved_chunks]

    if "metadata" not in state or state["metadata"] is None:
        state["metadata"] = {}
    state["metadata"]["model_used"] = qa_resp.model_used
    state["metadata"]["is_grounded"] = qa_resp.is_grounded

    return state


async def bug_node(state: AgentState) -> AgentState:
    """Bug Detection node: static analysis correlation and defect diagnosis."""
    state["current_step"] = "executing_bug_hunt"
    state["next_node"] = "format_node"

    repo_id = state.get("repo_id", "")
    query = state.get("user_query", "")

    req = BugHuntRequest(
        repo_id=repo_id,
        query=query,
    )
    hunt_resp = await bug_agent_service.hunt_bugs(req)

    state["diagnostic_findings"] = [f.model_dump() for f in hunt_resp.findings]
    state["final_response"] = hunt_resp.summary

    # Extract citation tags from findings
    citations = [f"{f.file_path}:{f.line_number}" for f in hunt_resp.findings]
    state["citations"] = sorted(list(set(citations)))

    if "metadata" not in state or state["metadata"] is None:
        state["metadata"] = {}
    state["metadata"]["total_bugs"] = hunt_resp.total_bugs
    state["metadata"]["critical_count"] = hunt_resp.critical_count
    state["metadata"]["high_count"] = hunt_resp.high_count
    state["metadata"]["medium_count"] = hunt_resp.medium_count
    state["metadata"]["low_count"] = hunt_resp.low_count
    state["metadata"]["model_used"] = hunt_resp.model_used

    return state


async def security_node(state: AgentState) -> AgentState:
    """Security node: vulnerability scanning and remediation."""
    state["current_step"] = "executing_security_audit"
    state["next_node"] = "format_node"

    repo_id = state.get("repo_id", "")
    query = state.get("user_query", "")

    req = SecurityAuditRequest(
        repo_id=repo_id,
        query=query,
    )
    audit_resp = await security_agent_service.audit_security(req)

    state["diagnostic_findings"] = [v.model_dump() for v in audit_resp.vulnerabilities]
    state["final_response"] = audit_resp.summary

    # Extract citation tags from vulnerabilities
    citations = [f"{v.file_path}:{v.line_number}" for v in audit_resp.vulnerabilities]
    state["citations"] = sorted(list(set(citations)))

    if "metadata" not in state or state["metadata"] is None:
        state["metadata"] = {}
    state["metadata"]["total_vulnerabilities"] = audit_resp.total_vulnerabilities
    state["metadata"]["critical_count"] = audit_resp.critical_count
    state["metadata"]["high_count"] = audit_resp.high_count
    state["metadata"]["medium_count"] = audit_resp.medium_count
    state["metadata"]["low_count"] = audit_resp.low_count
    state["metadata"]["model_used"] = audit_resp.model_used

    return state


async def test_node(state: AgentState) -> AgentState:
    """Test Generation node: test scaffold synthesis."""
    state["current_step"] = "executing_test_gen"
    state["next_node"] = "format_node"

    repo_id = state.get("repo_id", "")
    query = state.get("user_query", "")

    req = TestGenRequest(
        repo_id=repo_id,
        query=query,
    )
    test_resp = await test_agent_service.generate_tests(req)

    state["final_response"] = test_resp.summary
    state["citations"] = [test_resp.target_file] if test_resp.target_file else []

    if "metadata" not in state or state["metadata"] is None:
        state["metadata"] = {}
    state["metadata"]["framework"] = test_resp.framework.value
    state["metadata"]["target_symbol"] = test_resp.target_symbol
    state["metadata"]["target_file"] = test_resp.target_file
    state["metadata"]["total_tests"] = test_resp.total_tests
    state["metadata"]["model_used"] = test_resp.model_used

    return state


async def doc_node(state: AgentState) -> AgentState:
    """Documentation node: module summaries, docstrings, and Mermaid diagrams."""
    state["current_step"] = "executing_doc_gen"
    state["next_node"] = "format_node"

    repo_id = state.get("repo_id", "")
    query = state.get("user_query", "")

    req = DocGenRequest(
        repo_id=repo_id,
        query=query,
        include_mermaid=True,
    )
    doc_resp = await doc_agent_service.generate_documentation(req)

    state["final_response"] = doc_resp.markdown_documentation
    state["citations"] = [doc_resp.target_file] if doc_resp.target_file else []

    if "metadata" not in state or state["metadata"] is None:
        state["metadata"] = {}
    state["metadata"]["doc_format"] = doc_resp.doc_format.value
    state["metadata"]["target_file"] = doc_resp.target_file
    state["metadata"]["documented_symbols_count"] = len(doc_resp.documented_symbols)
    state["metadata"]["has_mermaid"] = doc_resp.mermaid_diagram is not None
    state["metadata"]["model_used"] = doc_resp.model_used

    return state


async def pr_node(state: AgentState) -> AgentState:
    """PR Review node: git diff analysis and review comment generation."""
    state["current_step"] = "executing_pr_review"
    repo_id = state.get("repo_id", "default-repo")
    query = state.get("user_query", "")

    # Extract optional PR number from query (e.g. "Review PR #42")
    pr_num = None
    pr_match = re.search(r"#(\d+)", query)
    if pr_match:
        pr_num = int(pr_match.group(1))

    raw_diff = state.get("metadata", {}).get("raw_diff") if state.get("metadata") else None
    req = PRReviewRequest(
        repo_id=repo_id,
        pr_number=pr_num,
        repo_full_name=repo_id if "/" in repo_id else None,
        raw_diff=raw_diff,
        query=query,
    )
    review_resp = await pr_review_agent_service.review_pull_request(req)

    state["final_response"] = review_resp.summary
    state["citations"] = review_resp.files_reviewed

    if "metadata" not in state or state["metadata"] is None:
        state["metadata"] = {}
    state["metadata"]["pr_verdict"] = review_resp.verdict.value
    state["metadata"]["pr_findings_count"] = len(review_resp.findings)
    state["metadata"]["files_reviewed"] = review_resp.files_reviewed
    state["metadata"]["model_used"] = review_resp.model_used

    state["next_node"] = "format_node"
    return state


async def format_node(state: AgentState) -> AgentState:
    """Format final response, append citations, and finalize output."""
    state["current_step"] = "formatting_output"
    citations = state.get("citations", [])

    if citations and state.get("final_response"):
        formatted_cites = "\n\n**Sources & Citations:**\n" + "\n".join(f"- `{c}`" for c in citations)
        state["final_response"] += formatted_cites

    return state


# ---------------------------------------------------------------------------
# Workflow Graph Builder & Engine
# ---------------------------------------------------------------------------

class WorkflowGraph:
    """Stateful workflow graph manager supporting conditional routing and step execution."""

    def __init__(self):
        self.nodes: Dict[str, Callable] = {}
        self.entry_point: str = "router_node"

    def add_node(self, name: str, func: Callable):
        self.nodes[name] = func

    def route_intent(self, state: AgentState) -> str:
        """Route to specialized sub-agent based on intent classification."""
        intent = state.get("intent", AgentIntent.CODE_QA.value)
        mapping = {
            AgentIntent.CODE_QA.value: "qa_node",
            AgentIntent.BUG_HUNT.value: "bug_node",
            AgentIntent.SECURITY_AUDIT.value: "security_node",
            AgentIntent.TEST_GEN.value: "test_node",
            AgentIntent.DOC_GEN.value: "doc_node",
            AgentIntent.PR_REVIEW.value: "pr_node",
        }
        return mapping.get(intent, "qa_node")

    async def execute(self, initial_state: AgentState) -> AgentState:
        """Run workflow from router through specialized subagent to output formatting."""
        state = initial_state
        repo_id = state.get("repo_id", "")
        query = state.get("user_query", "")

        with trace_span(
            "devmind.agent.workflow",
            attributes={
                "devmind.repo_id": repo_id,
                "devmind.query": query[:128],
                "devmind.component": "orchestrator",
            },
        ):
            # Step 1: Router node
            if "router_node" in self.nodes:
                with trace_agent_node("router_node", repo_id=repo_id, step=state.get("current_step")):
                    t0 = time.perf_counter()
                    state = await self.nodes["router_node"](state)
                    metrics_manager.record_agent_node("router_node", "success", time.perf_counter() - t0)

            if state.get("intent"):
                metrics_manager.record_agent_intent(state["intent"])

            # Step 2: Route conditionally to specialized subagent
            target_node = self.route_intent(state)
            if target_node in self.nodes:
                with trace_agent_node(target_node, repo_id=repo_id, intent=state.get("intent")):
                    t1 = time.perf_counter()
                    state = await self.nodes[target_node](state)
                    metrics_manager.record_agent_node(target_node, "success", time.perf_counter() - t1)

            # Conditional Interrupt Gate: if node requested human approval, pause workflow execution cleanly
            if state.get("interrupted"):
                return state

            # Step 3: Formatting & Citation node
            if "format_node" in self.nodes:
                with trace_agent_node("format_node", repo_id=repo_id, intent=state.get("intent")):
                    t2 = time.perf_counter()
                    state = await self.nodes["format_node"](state)
                    metrics_manager.record_agent_node("format_node", "success", time.perf_counter() - t2)

            metrics_manager.record_citations(state.get("citations", []))
            state["current_step"] = "completed"
            return state


def build_devmind_graph() -> WorkflowGraph:
    """Construct and configure the central DevMind multi-agent workflow graph."""
    graph = WorkflowGraph()

    # Register nodes
    graph.add_node("router_node", router_node)
    graph.add_node("qa_node", qa_node)
    graph.add_node("bug_node", bug_node)
    graph.add_node("security_node", security_node)
    graph.add_node("test_node", test_node)
    graph.add_node("doc_node", doc_node)
    graph.add_node("pr_node", pr_node)
    graph.add_node("format_node", format_node)

    return graph


devmind_workflow = build_devmind_graph()
