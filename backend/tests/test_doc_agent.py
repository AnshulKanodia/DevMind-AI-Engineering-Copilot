import pytest
from app.agents.graph import build_devmind_graph
from app.agents.state import create_initial_state
from app.schemas.chunk import CodeChunk
from app.schemas.doc_gen import DocFormat, DocGenRequest, MermaidDiagramType
from app.services.doc_agent import doc_agent_service
from app.services.hybrid_retriever import hybrid_retriever_service


@pytest.mark.asyncio
async def test_google_docstring_and_mermaid_flowchart():
    source = """
import httpx
from app.core.config import get_settings

class PaymentProcessor:
    def charge_card(self, amount: float, currency: str) -> bool:
        return True

async def initiate_refund(tx_id: str, reason: str) -> dict:
    client = httpx.AsyncClient()
    return {"status": "refunded", "tx_id": tx_id}
"""
    req = DocGenRequest(
        repo_id="test-doc-repo",
        target_path="app/services/payments.py",
        code_snippet=source,
        doc_format=DocFormat.GOOGLE,
        include_mermaid=True,
        diagram_type=MermaidDiagramType.FLOWCHART,
    )
    resp = await doc_agent_service.generate_documentation(req, force_offline=True)

    assert resp.doc_format == DocFormat.GOOGLE
    assert len(resp.documented_symbols) >= 2
    assert resp.mermaid_diagram is not None
    assert "flowchart TD" in resp.mermaid_diagram
    assert "PaymentProcessor" in resp.markdown_documentation
    assert "Args:" in resp.markdown_documentation
    assert "Returns:" in resp.markdown_documentation


@pytest.mark.asyncio
async def test_sphinx_docstring_format():
    source = """
def compute_checksum(payload: bytes, salt: str) -> str:
    return "abc123checksum"
"""
    req = DocGenRequest(
        repo_id="test-sphinx-repo",
        target_path="app/utils/crypto.py",
        code_snippet=source,
        doc_format=DocFormat.SPHINX,
        include_mermaid=False,
    )
    resp = await doc_agent_service.generate_documentation(req, force_offline=True)

    assert resp.doc_format == DocFormat.SPHINX
    assert resp.mermaid_diagram is None
    assert ":param payload:" in resp.documented_symbols[0].generated_docstring
    assert ":rtype: str" in resp.documented_symbols[0].generated_docstring


@pytest.mark.asyncio
async def test_jsdoc_format_auto_detection():
    ts_source = """
export async function syncRepository(repoId: string, branch: string) {
    return { synced: true };
}
"""
    req = DocGenRequest(
        repo_id="test-ts-doc",
        target_path="frontend/src/services/repo.ts",
        code_snippet=ts_source,
    )
    resp = await doc_agent_service.generate_documentation(req, force_offline=True)

    assert resp.doc_format == DocFormat.JSDOC
    assert "@param" in resp.documented_symbols[0].generated_docstring
    assert "@returns" in resp.documented_symbols[0].generated_docstring


@pytest.mark.asyncio
async def test_mermaid_class_and_sequence_diagrams():
    source = """
class BaseAgent:
    def execute(self):
        pass

class SecurityAgent(BaseAgent):
    def scan(self):
        pass
"""
    class_req = DocGenRequest(
        repo_id="test-mermaid-repo",
        target_path="app/agents/base.py",
        code_snippet=source,
        diagram_type=MermaidDiagramType.CLASS,
    )
    class_resp = await doc_agent_service.generate_documentation(class_req, force_offline=True)
    assert "classDiagram" in class_resp.mermaid_diagram
    assert "BaseAgent <|-- SecurityAgent" in class_resp.mermaid_diagram

    seq_req = DocGenRequest(
        repo_id="test-mermaid-repo",
        target_path="app/agents/base.py",
        code_snippet=source,
        diagram_type=MermaidDiagramType.SEQUENCE,
    )
    seq_resp = await doc_agent_service.generate_documentation(seq_req, force_offline=True)
    assert "sequenceDiagram" in seq_resp.mermaid_diagram


@pytest.mark.asyncio
async def test_workflow_graph_doc_node_execution():
    repo_id = "test-graph-doc-repo"
    chunk = CodeChunk(
        chunk_id="chk_doc_1",
        repo_id=repo_id,
        file_path="app/services/indexer.py",
        symbol_name="index_repository_vectors",
        start_line=1,
        end_line=20,
        content="""async def index_repository_vectors(repo_id: str, batch_size: int) -> int:
    '''Indexes repository chunks into MongoDB Atlas Vector Search.'''
    return 42
""",
        token_count=16,
        metadata={"language": "python"},
    )
    hybrid_retriever_service.register_repo_chunks(repo_id, [chunk])

    graph = build_devmind_graph()
    initial_state = create_initial_state(
        repo_id=repo_id,
        user_query="Generate architecture documentation and README diagram for the repository",
    )

    final_state = await graph.execute(initial_state)

    assert final_state["current_step"] == "completed"
    assert final_state["intent"] == "doc_gen"
    assert "```mermaid" in final_state["final_response"]
    assert "index_repository_vectors" in final_state["final_response"]
    assert final_state["metadata"]["has_mermaid"] is True
    assert final_state["metadata"]["documented_symbols_count"] >= 1
