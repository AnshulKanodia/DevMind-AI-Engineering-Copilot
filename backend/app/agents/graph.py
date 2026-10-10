import logging
from typing import Any, Callable, Dict, List, Optional

from app.agents.state import AgentIntent, AgentState
from app.services.qa_agent import qa_agent_service
from app.services.router_agent import router_agent_service

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
    """Bug Detection node: static analysis correlation."""
    state["current_step"] = "executing_bug_hunt"
    state["next_node"] = "format_node"
    return state


async def security_node(state: AgentState) -> AgentState:
    """Security node: vulnerability scanning and remediation."""
    state["current_step"] = "executing_security_audit"
    state["next_node"] = "format_node"
    return state


async def test_node(state: AgentState) -> AgentState:
    """Test Generation node: test scaffold synthesis."""
    state["current_step"] = "executing_test_gen"
    state["next_node"] = "format_node"
    return state


async def doc_node(state: AgentState) -> AgentState:
    """Documentation node: module summaries and markdown synthesis."""
    state["current_step"] = "executing_doc_gen"
    state["next_node"] = "format_node"
    return state


async def pr_node(state: AgentState) -> AgentState:
    """PR Review node: git diff analysis and review comment generation."""
    state["current_step"] = "executing_pr_review"
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

        # Step 1: Router node
        if "router_node" in self.nodes:
            state = await self.nodes["router_node"](state)

        # Step 2: Route conditionally to specialized subagent
        target_node = self.route_intent(state)
        if target_node in self.nodes:
            state = await self.nodes[target_node](state)

        # Step 3: Formatting & Citation node
        if "format_node" in self.nodes:
            state = await self.nodes["format_node"](state)

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
