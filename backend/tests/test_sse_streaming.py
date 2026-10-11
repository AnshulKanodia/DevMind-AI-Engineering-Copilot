import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chunk import CodeChunk
from app.schemas.streaming import AgentChatRequest, SSEEventType
from app.services.hybrid_retriever import hybrid_retriever_service
from app.services.streaming_service import agent_streaming_service

client = TestClient(app)


def test_format_sse_frame():
    frame = agent_streaming_service.format_sse_frame(
        SSEEventType.NODE_START,
        {"node": "router_node"},
    )
    assert frame.startswith("event: node_start\n")
    assert "\ndata: " in frame
    assert frame.endswith("\n\n")

    data_line = frame.splitlines()[1]
    payload = json.loads(data_line[len("data: ") :])
    assert payload["event"] == "node_start"
    assert payload["data"]["node"] == "router_node"
    assert "timestamp" in payload


def test_chunk_response_tokens():
    sample_text = "A" * 100
    chunks = agent_streaming_service.chunk_response_tokens(sample_text, chunk_size=30)
    assert len(chunks) == 4
    assert "".join(chunks) == sample_text


@pytest.mark.asyncio
async def test_stream_workflow_event_sequence():
    repo_id = "test-sse-repo"
    chunk = CodeChunk(
        chunk_id="chk_sse_1",
        repo_id=repo_id,
        file_path="app/core/security.py",
        symbol_name="create_jwt_token",
        start_line=15,
        end_line=30,
        content="def create_jwt_token(subject: str) -> str:\n    return 'jwt_signed_token'",
        token_count=14,
        metadata={"language": "python"},
    )
    hybrid_retriever_service.register_repo_chunks(repo_id, [chunk])

    req = AgentChatRequest(
        repo_id=repo_id,
        query="How does create_jwt_token sign tokens?",
    )

    frames = []
    async for frame in agent_streaming_service.stream_workflow(req):
        frames.append(frame)

    assert len(frames) >= 6
    event_types = [
        line.split(": ")[1]
        for f in frames
        for line in f.splitlines()
        if line.startswith("event: ")
    ]
    assert "node_start" in event_types
    assert "intent_classified" in event_types
    assert "retrieval_complete" in event_types
    assert "token" in event_types
    assert "citations" in event_types
    assert "final_response" in event_types
    assert event_types[-1] == "done"


def test_agent_chat_rest_endpoint():
    repo_id = "test-endpoint-chat-repo"
    chunk = CodeChunk(
        chunk_id="chk_api_1",
        repo_id=repo_id,
        file_path="app/services/cache.py",
        symbol_name="get_cached_value",
        start_line=5,
        end_line=18,
        content="def get_cached_value(key: str):\n    return redis_client.get(key)",
        token_count=12,
        metadata={"language": "python"},
    )
    hybrid_retriever_service.register_repo_chunks(repo_id, [chunk])

    resp = client.post(
        "/api/v1/agents/chat",
        json={
            "repo_id": repo_id,
            "query": "Where is get_cached_value implemented?",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["repo_id"] == repo_id
    assert body["intent"] == "code_qa"
    assert "app/services/cache.py:5-18" in body["citations"]
    assert "get_cached_value" in body["final_response"]


def test_agent_stream_sse_endpoint():
    repo_id = "test-endpoint-stream-repo"
    resp = client.post(
        "/api/v1/agents/stream",
        json={
            "repo_id": repo_id,
            "query": "Scan for SQLi security vulnerabilities",
        },
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    assert "event: intent_classified" in resp.text
    assert "event: final_response" in resp.text
    assert "event: done" in resp.text
