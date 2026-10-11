import pytest
from app.agents.graph import build_devmind_graph
from app.agents.state import create_initial_state
from app.schemas.chunk import CodeChunk
from app.schemas.test_gen import TestFramework, TestGenRequest
from app.services.hybrid_retriever import hybrid_retriever_service
from app.services.test_agent import test_agent_service


def test_detect_framework():
    assert test_agent_service.detect_framework("app/services/auth.py") == TestFramework.PYTEST
    assert test_agent_service.detect_framework("src/components/Button.tsx") == TestFramework.JEST
    assert test_agent_service.detect_framework("pkg/server/handler.go") == TestFramework.GO_TEST
    assert test_agent_service.detect_framework("src/Main.java") == TestFramework.JUNIT


def test_extract_python_targets():
    source = """
async def process_payment(user_id: str, amount: float):
    if amount <= 0:
        raise ValueError("Amount must be positive")
    receipt = stripe_client.charge(user_id, amount)
    db_repo.record_transaction(receipt)
    return receipt
"""
    targets = test_agent_service.extract_python_targets(source)
    assert len(targets) == 1

    t = targets[0]
    assert t.name == "process_payment"
    assert t.is_async is True
    assert t.params == ["user_id", "amount"]
    assert "ValueError" in t.raises
    assert "stripe_client.charge" in t.external_calls
    assert "db_repo.record_transaction" in t.external_calls


@pytest.mark.asyncio
async def test_generate_pytest_suite_from_snippet():
    source = """
def calculate_discount(price: float, discount_rate: float) -> float:
    if discount_rate < 0 or discount_rate > 1:
        raise ValueError("Invalid discount rate")
    audit_logger.info(price)
    return price * (1.0 - discount_rate)
"""
    req = TestGenRequest(
        repo_id="test-repo",
        target_symbol="calculate_discount",
        target_path="backend/app/services/pricing.py",
        code_snippet=source,
    )
    resp = await test_agent_service.generate_tests(req, force_offline=True)

    assert resp.framework == TestFramework.PYTEST
    assert resp.target_symbol == "calculate_discount"
    assert resp.total_tests == 4
    categories = {tc.category for tc in resp.test_cases}
    assert "happy_path" in categories
    assert "edge_case" in categories
    assert "error_handling" in categories
    assert "mock_isolation" in categories
    assert "pytest.raises(ValueError)" in resp.full_test_suite_code
    assert "patch(\"app.services.pricing.audit_logger\"" in resp.full_test_suite_code


@pytest.mark.asyncio
async def test_generate_jest_suite_from_typescript():
    ts_code = """
export async function fetchUserProfile(userId: string) {
    const res = await apiClient.get(`/users/${userId}`);
    return res.data;
}
"""
    req = TestGenRequest(
        repo_id="test-ts-repo",
        target_symbol="fetchUserProfile",
        target_path="frontend/src/api/users.ts",
        code_snippet=ts_code,
    )
    resp = await test_agent_service.generate_tests(req, force_offline=True)

    assert resp.framework == TestFramework.JEST
    assert resp.target_symbol == "fetchUserProfile"
    assert resp.total_tests == 3
    assert "describe('fetchUserProfile Unit Test Suite'" in resp.full_test_suite_code
    assert "jest.fn()" in resp.full_test_suite_code


@pytest.mark.asyncio
async def test_workflow_graph_test_node_execution():
    repo_id = "test-graph-testgen-repo"
    chunk = CodeChunk(
        chunk_id="chk_test_1",
        repo_id=repo_id,
        file_path="app/utils/validators.py",
        symbol_name="validate_email_address",
        start_line=10,
        end_line=22,
        content="""def validate_email_address(email: str) -> bool:
    if not email or "@" not in email:
        raise ValueError("Malformed email")
    return True
""",
        token_count=15,
        metadata={"language": "python"},
    )
    hybrid_retriever_service.register_repo_chunks(repo_id, [chunk])

    graph = build_devmind_graph()
    initial_state = create_initial_state(
        repo_id=repo_id,
        user_query="Generate pytest unit tests with mock assertions for validate_email_address",
    )

    final_state = await graph.execute(initial_state)

    assert final_state["current_step"] == "completed"
    assert final_state["intent"] == "test_gen"
    assert "validate_email_address" in final_state["final_response"]
    assert final_state["metadata"]["framework"] == "pytest"
    assert final_state["metadata"]["total_tests"] >= 3
