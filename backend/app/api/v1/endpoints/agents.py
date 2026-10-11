from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.streaming import AgentChatRequest, AgentChatResponse
from app.services.streaming_service import agent_streaming_service

router = APIRouter()


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat_endpoint(request: AgentChatRequest) -> AgentChatResponse:
    """Execute multi-agent workflow and return complete structured JSON response."""
    return await agent_streaming_service.execute_sync(request)


@router.post("/stream")
async def agent_stream_endpoint(request: AgentChatRequest) -> StreamingResponse:
    """Stream real-time Server-Sent Events (SSE) across LangGraph nodes, tokens, and citations."""
    event_generator = agent_streaming_service.stream_workflow(request)
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers=headers,
    )
