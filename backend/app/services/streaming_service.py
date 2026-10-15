from datetime import datetime, timezone
import json
from typing import Any, AsyncGenerator, Dict, List

from app.agents.graph import devmind_workflow
from app.agents.state import AgentState, create_initial_state
from app.core.telemetry import trace_span
from app.schemas.streaming import AgentChatRequest, AgentChatResponse, SSEEventType


class AgentStreamingService:
    """Server-Sent Events (SSE) streaming orchestrator for LangGraph multi-agent execution."""

    @staticmethod
    def format_sse_frame(event_type: SSEEventType, data: Dict[str, Any]) -> str:
        """Serialize an event type and payload dictionary into a standard W3C SSE frame."""
        envelope = {
            "event": event_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        return f"event: {event_type.value}\ndata: {json.dumps(envelope)}\n\n"

    @staticmethod
    def chunk_response_tokens(text: str, chunk_size: int = 48) -> List[str]:
        """Split a synthesized response into token-like chunks for progressive UI rendering."""
        if not text:
            return []
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    async def execute_sync(self, request: AgentChatRequest) -> AgentChatResponse:
        """Run full multi-agent workflow and return complete JSON response."""
        with trace_span(
            "devmind.agent.chat_sync",
            attributes={
                "devmind.repo_id": request.repo_id,
                "devmind.query": request.query[:128],
            },
        ):
            initial_state = create_initial_state(
                repo_id=request.repo_id,
                user_query=request.query,
                messages=request.messages,
            )
            final_state = await devmind_workflow.execute(initial_state)
            meta = final_state.get("metadata", {}) or {}

            return AgentChatResponse(
                repo_id=request.repo_id,
                query=request.query,
                intent=final_state.get("intent", "code_qa"),
                target_subagent=meta.get("target_subagent", "Code Q&A Agent"),
                final_response=final_state.get("final_response") or "",
                citations=final_state.get("citations", []),
                retrieved_chunks=final_state.get("retrieved_chunks", []),
                diagnostic_findings=final_state.get("diagnostic_findings", []),
                metadata=meta,
            )

    async def stream_workflow(
        self, request: AgentChatRequest
    ) -> AsyncGenerator[str, None]:
        """Execute LangGraph nodes step-by-step, yielding real-time SSE frames."""
        with trace_span(
            "devmind.agent.stream_session",
            attributes={
                "devmind.repo_id": request.repo_id,
                "devmind.query": request.query[:128],
            },
        ):
            state: AgentState = create_initial_state(
                repo_id=request.repo_id,
                user_query=request.query,
                messages=request.messages,
            )

            try:
                # 1. Router Node Execution
                yield self.format_sse_frame(
                    SSEEventType.NODE_START,
                    {"node": "router_node", "status": "Analyzing developer intent..."},
                )
                if "router_node" in devmind_workflow.nodes:
                    state = await devmind_workflow.nodes["router_node"](state)

                meta = state.get("metadata", {}) or {}
                yield self.format_sse_frame(
                    SSEEventType.INTENT_CLASSIFIED,
                    {
                        "intent": state.get("intent"),
                        "confidence": meta.get("router_confidence", 0.9),
                        "target_subagent": meta.get("target_subagent", "Code Q&A Agent"),
                        "reasoning": meta.get("router_reasoning", ""),
                    },
                )
                yield self.format_sse_frame(
                    SSEEventType.NODE_COMPLETE,
                    {"node": "router_node"},
                )

                # 2. Target Subagent Node Execution
                target_node = devmind_workflow.route_intent(state)
                yield self.format_sse_frame(
                    SSEEventType.NODE_START,
                    {
                        "node": target_node,
                        "subagent": meta.get("target_subagent", target_node),
                        "status": f"Executing {meta.get('target_subagent', target_node)}...",
                    },
                )

                if target_node in devmind_workflow.nodes:
                    state = await devmind_workflow.nodes[target_node](state)

                # Emit retrieval / diagnostic intermediate event
                yield self.format_sse_frame(
                    SSEEventType.RETRIEVAL_COMPLETE,
                    {
                        "node": target_node,
                        "retrieved_chunks_count": len(state.get("retrieved_chunks", [])),
                        "diagnostic_findings_count": len(state.get("diagnostic_findings", [])),
                    },
                )
                yield self.format_sse_frame(
                    SSEEventType.NODE_COMPLETE,
                    {"node": target_node},
                )

                # 3. Formatting & Citation Node Execution
                yield self.format_sse_frame(
                    SSEEventType.NODE_START,
                    {"node": "format_node", "status": "Formatting response and verifying citations..."},
                )
                if "format_node" in devmind_workflow.nodes:
                    state = await devmind_workflow.nodes["format_node"](state)

                final_text = state.get("final_response") or ""

                # 4. Stream incremental response tokens
                for idx, token_chunk in enumerate(self.chunk_response_tokens(final_text)):
                    yield self.format_sse_frame(
                        SSEEventType.TOKEN,
                        {"index": idx, "content": token_chunk},
                    )

                # 5. Emit Citations event
                citations = state.get("citations", [])
                yield self.format_sse_frame(
                    SSEEventType.CITATIONS,
                    {"citations": citations, "count": len(citations)},
                )

                # 6. Emit Final Response & Done events
                state["current_step"] = "completed"
                yield self.format_sse_frame(
                    SSEEventType.FINAL_RESPONSE,
                    {
                        "repo_id": request.repo_id,
                        "intent": state.get("intent"),
                        "final_response": final_text,
                        "citations": citations,
                        "metadata": state.get("metadata", {}),
                    },
                )
                yield self.format_sse_frame(
                    SSEEventType.DONE,
                    {"status": "[DONE]"},
                )

            except Exception as exc:
                yield self.format_sse_frame(
                    SSEEventType.ERROR,
                    {"error": str(exc)},
                )


agent_streaming_service = AgentStreamingService()
