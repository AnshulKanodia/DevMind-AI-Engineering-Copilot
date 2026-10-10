import pytest
from app.agents.graph import build_devmind_graph
from app.agents.state import create_initial_state
from app.schemas.chunk import CodeChunk
from app.schemas.retrieval import RetrievedChunk
from app.services.hybrid_retriever import hybrid_retriever_service
from app.services.qa_agent import qa_agent_service


def test_format_context():
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            file_path="app/core/security.py",
            symbol_name="verify_password",
            start_line=15,
            end_line=25,
            content="def verify_password(plain, hashed):\n    return pwd_context.verify(plain, hashed)",
            combined_score=0.95,
            dense_score=0.9,
            sparse_score=1.0,
            citation_label="app/core/security.py:15-25",
            metadata={"language": "python"},
        ),
        RetrievedChunk(
            chunk_id="c2",
            file_path="app/core/security.py",
            symbol_name="create_access_token",
            start_line=30,
            end_line=45,
            content="def create_access_token(data, expires_delta=None):\n    ...",
            combined_score=0.88,
            dense_score=0.85,
            sparse_score=0.9,
            citation_label="app/core/security.py:30-45",
            metadata={"language": "python"},
        ),
    ]

    formatted = qa_agent_service.format_context(chunks)
    assert "app/core/security.py" in formatted
    assert "Lines 15-25" in formatted
    assert "verify_password" in formatted
    assert "[app/core/security.py:15-25]" in formatted
    assert "```python" in formatted


def test_format_context_empty():
    formatted = qa_agent_service.format_context([])
    assert "No relevant code snippets were found" in formatted


def test_extract_citations():
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            file_path="app/main.py",
            start_line=10,
            end_line=20,
            content="app = FastAPI()",
            combined_score=0.9,
            dense_score=0.9,
            sparse_score=0.9,
            citation_label="app/main.py:10-20",
        )
    ]
    text = "The application entrypoint is registered in `[app/main.py:10-20]`."
    citations = qa_agent_service.extract_citations(text, chunks)
    assert citations == ["app/main.py:10-20"]


@pytest.mark.asyncio
async def test_qa_agent_empty_retrieval_response():
    resp = await qa_agent_service.answer_query(
        repo_id="nonexistent-repo-1234",
        query="Where is the quantum teleportation engine?",
        force_offline=True,
    )
    assert resp.is_grounded is False
    assert "not found in the provided context" in resp.answer
    assert resp.citations == []
    assert resp.retrieved_chunks == []


@pytest.mark.asyncio
async def test_qa_agent_mock_grounded_answer():
    repo_id = "test-qa-repo"
    test_chunk = CodeChunk(
        chunk_id="chk_auth_1",
        repo_id=repo_id,
        file_path="app/services/auth.py",
        symbol_name="authenticate_user",
        start_line=40,
        end_line=55,
        content="async def authenticate_user(username, password):\n    user = get_user(username)\n    return user",
        token_count=18,
        metadata={"language": "python"},
    )

    # Index into hybrid retriever
    hybrid_retriever_service.index_corpus(repo_id, [test_chunk])

    resp = await qa_agent_service.answer_query(
        repo_id=repo_id,
        query="How does authenticate_user verify credentials?",
        force_offline=True,
    )

    assert resp.is_grounded is True
    assert "authenticate_user" in resp.answer
    assert "app/services/auth.py:40-55" in resp.citations
    assert len(resp.detailed_citations) >= 1
    assert resp.detailed_citations[0].file_path == "app/services/auth.py"
    assert resp.detailed_citations[0].start_line == 40
    assert resp.detailed_citations[0].end_line == 55


@pytest.mark.asyncio
async def test_workflow_graph_qa_node_execution():
    repo_id = "test-graph-qa"
    sample_chunk = CodeChunk(
        chunk_id="chk_db_1",
        repo_id=repo_id,
        file_path="app/core/database.py",
        symbol_name="get_database_client",
        start_line=12,
        end_line=24,
        content="def get_database_client():\n    return AsyncIOMotorClient()",
        token_count=12,
        metadata={"language": "python"},
    )
    hybrid_retriever_service.index_corpus(repo_id, [sample_chunk])

    graph = build_devmind_graph()
    initial_state = create_initial_state(
        repo_id=repo_id,
        user_query="Where is the database client connection initialized?",
    )

    result_state = await graph.execute(initial_state)

    assert result_state["current_step"] == "completed"
    assert result_state["intent"] == "code_qa"
    assert result_state["final_response"] is not None
    assert "app/core/database.py:12-24" in result_state["final_response"]
    assert len(result_state["retrieved_chunks"]) > 0
    assert result_state["metadata"]["is_grounded"] is True
