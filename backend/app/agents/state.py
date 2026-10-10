from enum import Enum
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AgentIntent(str, Enum):
    CODE_QA = "code_qa"
    BUG_HUNT = "bug_hunt"
    SECURITY_AUDIT = "security_audit"
    TEST_GEN = "test_gen"
    DOC_GEN = "doc_gen"
    PR_REVIEW = "pr_review"
    UNKNOWN = "unknown"


class AgentState(TypedDict, total=False):
    """Global state container for LangGraph multi-agent execution workflows."""

    # Session & context identifiers
    repo_id: str
    user_query: str
    messages: List[Dict[str, Any]]

    # Routing & Planning
    intent: str
    next_node: str
    current_step: str
    iteration_count: int

    # RAG Retrieval & Context
    retrieved_chunks: List[Dict[str, Any]]
    citations: List[str]

    # Diagnostic tools & static analysis findings
    diagnostic_findings: List[Dict[str, Any]]
    diff_context: Optional[str]

    # Results & Status
    final_response: Optional[str]
    metadata: Dict[str, Any]
    error: Optional[str]


def create_initial_state(
    repo_id: str,
    user_query: str,
    messages: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AgentState:
    """Initialize a clean AgentState payload for a new user query."""
    return {
        "repo_id": repo_id,
        "user_query": user_query,
        "messages": messages or [{"role": "user", "content": user_query}],
        "intent": AgentIntent.UNKNOWN.value,
        "next_node": "router_node",
        "current_step": "initialized",
        "iteration_count": 0,
        "retrieved_chunks": [],
        "citations": [],
        "diagnostic_findings": [],
        "diff_context": None,
        "final_response": None,
        "metadata": metadata or {},
        "error": None,
    }
