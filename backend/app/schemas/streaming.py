from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SSEEventType(str, Enum):
    """Standardized Server-Sent Event types for LangGraph agent streaming."""
    NODE_START = "node_start"
    NODE_COMPLETE = "node_complete"
    INTENT_CLASSIFIED = "intent_classified"
    RETRIEVAL_COMPLETE = "retrieval_complete"
    TOKEN = "token"
    CITATIONS = "citations"
    FINAL_RESPONSE = "final_response"
    ERROR = "error"
    DONE = "done"


class SSEStreamEvent(BaseModel):
    """Structured SSE frame payload."""

    event: SSEEventType = Field(..., description="Event category")
    data: Dict[str, Any] = Field(..., description="JSON payload for the event")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp")


class AgentChatRequest(BaseModel):
    """Request payload for synchronous or streaming multi-agent copilot queries."""

    repo_id: str = Field(..., description="Target repository identifier")
    query: str = Field(..., description="Developer natural language question or command")
    session_id: Optional[str] = Field(
        default=None, description="Optional conversation session identifier"
    )
    messages: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Optional prior conversation history"
    )


class AgentChatResponse(BaseModel):
    """Complete multi-agent workflow response payload."""

    repo_id: str
    query: str
    intent: str = Field(..., description="Classified intent e.g. 'code_qa', 'bug_hunt'")
    target_subagent: str = Field(..., description="Name of the specialized agent that handled the request")
    final_response: str = Field(..., description="Formatted markdown response with citations")
    citations: List[str] = Field(default_factory=list, description="Source file & line citations")
    retrieved_chunks: List[Dict[str, Any]] = Field(
        default_factory=list, description="Retrieved code context snippets"
    )
    diagnostic_findings: List[Dict[str, Any]] = Field(
        default_factory=list, description="Static analysis or security findings if applicable"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Execution telemetry and model metadata"
    )
