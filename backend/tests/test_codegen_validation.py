import ast
import pytest

from app.agents.graph import build_devmind_graph
from app.agents.state import create_initial_state
from app.schemas.doc_gen import DocFormat, DocGenRequest, MermaidDiagramType
from app.schemas.test_gen import TestFramework, TestGenRequest
from app.services.doc_agent import doc_agent_service
from app.services.test_agent import test_agent_service


# ============================================================================
# Synthetic Target Modules for Codegen Validation
# ============================================================================

SAMPLE_PAYMENT_SERVICE_PY = """import httpx
from typing import Dict, Any, Optional


class PaymentGatewayError(Exception):
    \"\"\"Raised when upstream payment processor rejects a transaction.\"\"\"
    pass


async def process_stripe_charge(
    customer_id: str,
    amount_cents: int,
    currency: str = "USD",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if amount_cents <= 0:
        raise ValueError("Charge amount must be strictly positive")
    if not customer_id.strip():
        raise KeyError("Customer identifier is required")

    payload = {
        "customer": customer_id,
        "amount": amount_cents,
        "currency": currency.upper(),
        "metadata": metadata or {},
    }
    response = await httpx.post("https://api.stripe.com/v1/charges", json=payload)
    audit_entry = record_transaction_event(customer_id, amount_cents)
    return {"status": "succeeded", "charge": response, "audit": audit_entry}


def calculate_tiered_fee(subtotal: float, discount_rate: float = 0.0) -> float:
    if subtotal < 0:
        raise ValueError("Subtotal cannot be negative")
    if discount_rate < 0.0 or discount_rate > 1.0:
        raise ValueError("Discount rate must be between 0.0 and 1.0")
    net_amount = subtotal * (1.0 - discount_rate)
    return round(net_amount * 0.029 + 0.30, 2)
"""

SAMPLE_TS_AUTH_CLIENT = """export async function refreshAccessToken(refreshToken: string, clientId: string): Promise<string> {
    if (!refreshToken) {
        throw new Error("Refresh token is required");
    }
    const response = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        body: JSON.stringify({ refreshToken, clientId }),
    });
    const data = await response.json();
    return data.accessToken;
}
"""


# ============================================================================
# 1. Generated Python Test Suite AST & Bytecode Compilation Validation
# ============================================================================


@pytest.mark.asyncio
async def test_generated_pytest_suite_compiles_cleanly_for_async_function():
    """Verify generated pytest suite for an async function with raises and external calls is 100% valid Python AST."""
    req = TestGenRequest(
        repo_id="codegen-val-repo",
        target_symbol="process_stripe_charge",
        target_path="app/services/payment_service.py",
        code_snippet=SAMPLE_PAYMENT_SERVICE_PY,
        framework=TestFramework.PYTEST,
    )
    res = await test_agent_service.generate_tests(req, force_offline=True)

    assert res.framework == TestFramework.PYTEST
    assert res.target_symbol == "process_stripe_charge"
    assert res.total_tests >= 4

    # 1. Parse full test suite with ast.parse and compile to Python bytecode
    parsed_suite = ast.parse(res.full_test_suite_code)
    compiled_code = compile(
        parsed_suite, filename="test_payment_service.py", mode="exec"
    )
    assert compiled_code is not None

    # 2. Verify each individual test case snippet also parses cleanly via ast.parse
    for tc in res.test_cases:
        tc_tree = ast.parse(tc.test_code)
        func_nodes = [
            n
            for n in ast.walk(tc_tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert len(func_nodes) >= 1
        assert func_nodes[0].name.startswith("test_")

        # Ensure every test case contains at least one assert or `with pytest.raises(...)`
        has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(tc_tree))
        has_raises_ctx = any(isinstance(n, ast.With) for n in ast.walk(tc_tree))
        assert has_assert or has_raises_ctx, (
            f"Test case {tc.test_name} lacked both assert and pytest.raises context"
        )

    # 3. Verify all 4 test categories are represented
    categories = {tc.category for tc in res.test_cases}
    assert {
        "happy_path",
        "edge_case",
        "error_handling",
        "mock_isolation",
    }.issubset(categories)

    # 4. Verify external dependencies were detected and mocked
    mock_cases = [tc for tc in res.test_cases if tc.category == "mock_isolation"]
    assert len(mock_cases) >= 1
    assert len(mock_cases[0].mocked_dependencies) >= 1
    assert "patch(" in mock_cases[0].test_code


@pytest.mark.asyncio
async def test_generated_pytest_suite_compiles_cleanly_for_sync_function():
    """Verify generated pytest suite for a synchronous mathematical function compiles cleanly."""
    req = TestGenRequest(
        repo_id="codegen-val-repo",
        target_symbol="calculate_tiered_fee",
        target_path="app/services/payment_service.py",
        code_snippet=SAMPLE_PAYMENT_SERVICE_PY,
        framework=TestFramework.PYTEST,
    )
    res = await test_agent_service.generate_tests(req, force_offline=True)

    assert res.target_symbol == "calculate_tiered_fee"
    assert res.total_tests >= 3

    suite_tree = ast.parse(res.full_test_suite_code)
    compile(suite_tree, filename="test_calculate_tiered_fee.py", mode="exec")

    # Verify ValueError is tested in error_handling category
    error_cases = [tc for tc in res.test_cases if tc.category == "error_handling"]
    assert len(error_cases) >= 1
    assert "pytest.raises(ValueError)" in error_cases[0].test_code


# ============================================================================
# 2. Generated Jest / TypeScript Test Suite Structural Validation
# ============================================================================


@pytest.mark.asyncio
async def test_generated_jest_suite_has_balanced_delimiters_and_assertions():
    """Verify generated Jest test suite has balanced delimiters, describe/it blocks, expect(), and jest.fn()."""
    req = TestGenRequest(
        repo_id="codegen-val-repo",
        target_symbol="refreshAccessToken",
        target_path="frontend/src/lib/authClient.ts",
        code_snippet=SAMPLE_TS_AUTH_CLIENT,
    )
    res = await test_agent_service.generate_tests(req, force_offline=True)

    assert res.framework == TestFramework.JEST
    assert res.target_symbol == "refreshAccessToken"
    assert res.total_tests >= 3

    suite = res.full_test_suite_code
    # Check balanced delimiters
    assert suite.count("{") == suite.count("}")
    assert suite.count("(") == suite.count(")")
    assert suite.count("[") == suite.count("]")

    # Check Jest structural primitives
    assert "describe(" in suite
    assert "it(" in suite
    assert "expect(" in suite
    assert "jest.fn()" in suite or "jest.clearAllMocks()" in suite


# ============================================================================
# 3. Documentation Completeness & Docstring AST Injection Validation
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize("doc_format", [DocFormat.GOOGLE, DocFormat.SPHINX])
async def test_generated_python_docstrings_are_complete_and_valid_ast(doc_format: DocFormat):
    """Verify every symbol in Python module is documented, parameters are covered, and injected docstrings parse cleanly."""
    req = DocGenRequest(
        repo_id="codegen-val-repo",
        target_path="app/services/payment_service.py",
        code_snippet=SAMPLE_PAYMENT_SERVICE_PY,
        doc_format=doc_format,
        include_mermaid=True,
        diagram_type=MermaidDiagramType.FLOWCHART,
    )
    res = await doc_agent_service.generate_documentation(req, force_offline=True)

    assert res.doc_format == doc_format
    symbol_map = {s.symbol_name: s for s in res.documented_symbols}

    # Verify 100% symbol coverage across class, async function, and sync function
    assert {
        "PaymentGatewayError",
        "process_stripe_charge",
        "calculate_tiered_fee",
    }.issubset(set(symbol_map.keys()))

    # Verify all parameters of process_stripe_charge appear in its generated docstring
    charge_doc = symbol_map["process_stripe_charge"].generated_docstring
    for param_name in ("customer_id", "amount_cents", "currency", "metadata"):
        assert param_name in charge_doc

    # Verify format-specific markers
    if doc_format == DocFormat.GOOGLE:
        assert "Args:" in charge_doc
        assert "Returns:" in charge_doc
    elif doc_format == DocFormat.SPHINX:
        assert ":param customer_id:" in charge_doc
        assert ":rtype:" in charge_doc

    # Inject every generated docstring into a synthetic function/class body and parse via ast.parse()
    for sym in res.documented_symbols:
        indented_doc = "\n".join(
            f"    {line}" if line.strip() else ""
            for line in sym.generated_docstring.splitlines()
        )
        synthetic_module = f"{sym.signature}\n{indented_doc}\n    pass\n"
        parsed_mod = ast.parse(synthetic_module)
        assert len(parsed_mod.body) == 1
        extracted_doc = ast.get_docstring(parsed_mod.body[0])
        assert extracted_doc is not None and len(extracted_doc.strip()) > 10


@pytest.mark.asyncio
async def test_generated_jsdoc_for_typescript_module():
    """Verify TypeScript module automatically selects JSDoc format and documents parameters with @param/@returns."""
    req = DocGenRequest(
        repo_id="codegen-val-repo",
        target_path="frontend/src/lib/authClient.ts",
        code_snippet=SAMPLE_TS_AUTH_CLIENT,
    )
    res = await doc_agent_service.generate_documentation(req, force_offline=True)

    assert res.doc_format == DocFormat.JSDOC
    assert len(res.documented_symbols) >= 1
    jsdoc = res.documented_symbols[0].generated_docstring
    assert jsdoc.startswith("/**")
    assert jsdoc.endswith("*/")
    assert "@param" in jsdoc
    assert "@returns" in jsdoc


# ============================================================================
# 4. Mermaid Diagram Notation Validation
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "diagram_type,expected_header,expected_operator",
    [
        (MermaidDiagramType.FLOWCHART, "flowchart TD", "-->"),
        (MermaidDiagramType.CLASS, "classDiagram", "class "),
        (MermaidDiagramType.SEQUENCE, "sequenceDiagram", "->>"),
    ],
)
async def test_generated_mermaid_diagrams_adhere_to_syntax_rules(
    diagram_type: MermaidDiagramType,
    expected_header: str,
    expected_operator: str,
):
    """Verify generated Mermaid diagrams start with valid headers, contain valid edges, and embed in Markdown."""
    req = DocGenRequest(
        repo_id="codegen-val-repo",
        target_path="app/services/payment_service.py",
        code_snippet=SAMPLE_PAYMENT_SERVICE_PY,
        include_mermaid=True,
        diagram_type=diagram_type,
    )
    res = await doc_agent_service.generate_documentation(req, force_offline=True)

    assert res.mermaid_diagram is not None
    lines = [ln.strip() for ln in res.mermaid_diagram.strip().splitlines() if ln.strip()]
    assert lines[0] == expected_header
    assert expected_operator in res.mermaid_diagram
    assert f"```mermaid\n{res.mermaid_diagram}\n```" in res.markdown_documentation


# ============================================================================
# 5. End-to-End LangGraph Workflow Codegen Integration
# ============================================================================


@pytest.mark.asyncio
async def test_langgraph_workflow_end_to_end_test_and_doc_generation():
    """Verify LangGraph orchestrator routes and executes both test_gen and doc_gen intents."""
    graph = build_devmind_graph()

    test_state = await graph.execute(
        create_initial_state(
            repo_id="codegen-val-repo",
            user_query="Generate pytest unit tests with mocks for process_stripe_charge",
        )
    )
    assert test_state["intent"] == "test_gen"
    assert "### DevMind Unit Test Suite" in test_state["final_response"]
    assert "def test_" in test_state["final_response"]

    doc_state = await graph.execute(
        create_initial_state(
            repo_id="codegen-val-repo",
            user_query="Generate living architecture documentation and a Mermaid diagram for payment_service",
        )
    )
    assert doc_state["intent"] == "doc_gen"
    assert "```mermaid" in doc_state["final_response"]
    assert "## 1. Architectural Overview" in doc_state["final_response"]
