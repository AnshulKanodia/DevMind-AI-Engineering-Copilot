import pytest
from app.agents.graph import build_devmind_graph
from app.agents.state import create_initial_state
from app.schemas.bug import BugHuntRequest, BugSeverity
from app.schemas.chunk import CodeChunk
from app.services.bug_agent import bug_agent_service
from app.services.hybrid_retriever import hybrid_retriever_service


def test_bare_except_detection():
    source = """
def risky_operation():
    try:
        val = 10 / 0
    except:
        pass
"""
    findings = bug_agent_service.analyze_source_code(source, "service.py")
    rule_ids = [f.rule_id for f in findings]
    assert "DEV-BUG-001" in rule_ids

    bare_exc = next(f for f in findings if f.rule_id == "DEV-BUG-001")
    assert bare_exc.severity == BugSeverity.HIGH
    assert bare_exc.line_number in (5, 6)
    assert "Bare `except:`" in bare_exc.title


def test_mutable_default_argument_detection():
    source = """
def append_item(val, container=[]):
    container.append(val)
    return container
"""
    findings = bug_agent_service.analyze_source_code(source, "utils.py")
    rule_ids = [f.rule_id for f in findings]
    assert "DEV-BUG-002" in rule_ids

    mut_def = next(f for f in findings if f.rule_id == "DEV-BUG-002")
    assert mut_def.severity == BugSeverity.MEDIUM
    assert mut_def.symbol_name == "append_item"
    assert "mutable container" in mut_def.description.lower()


def test_unreachable_code_detection():
    source = """
def calculate_score(points):
    if points < 0:
        return 0
        print("Invalid negative points")
    return points * 2
"""
    findings = bug_agent_service.analyze_source_code(source, "scoring.py")
    rule_ids = [f.rule_id for f in findings]
    assert "DEV-BUG-003" in rule_ids

    dead_code = next(f for f in findings if f.rule_id == "DEV-BUG-003")
    assert dead_code.severity == BugSeverity.LOW
    assert dead_code.line_number == 5


def test_builtin_shadowing_detection():
    source = """
def lookup_item(id, type, list):
    return {"id": id, "type": type}
"""
    findings = bug_agent_service.analyze_source_code(source, "repo.py")
    rule_ids = [f.rule_id for f in findings]
    assert "DEV-BUG-005" in rule_ids
    shadowed = [f for f in findings if f.rule_id == "DEV-BUG-005"]
    assert len(shadowed) >= 2


def test_comparison_to_none_detection():
    source = """
def is_empty(val):
    if val == None:
        return True
    return False
"""
    findings = bug_agent_service.analyze_source_code(source, "checks.py")
    rule_ids = [f.rule_id for f in findings]
    assert "DEV-BUG-006" in rule_ids

    none_check = next(f for f in findings if f.rule_id == "DEV-BUG-006")
    assert "is None" in none_check.remediation


def test_multilanguage_heuristic_checks():
    js_source = """
function processData(input) {
    try {
        runTask(input);
    } catch (e) {}

    if (x = 10) {
        doSomething();
    }
}
"""
    findings = bug_agent_service.analyze_source_code(js_source, "processor.js")
    rule_ids = [f.rule_id for f in findings]
    assert "DEV-BUG-007" in rule_ids
    assert "DEV-BUG-008" in rule_ids


def test_clean_code_zero_findings():
    clean_python = """
def clean_function(data: list) -> int:
    '''Calculates sum of elements with proper error handling.'''
    try:
        return sum(data)
    except TypeError as e:
        logger.error("Invalid data types: %s", e)
        raise
"""
    findings = bug_agent_service.analyze_source_code(clean_python, "clean.py")
    assert len(findings) == 0


@pytest.mark.asyncio
async def test_hunt_bugs_direct_code_snippet():
    buggy_code = """
def query_user(user_id):
    try:
        user = fetch(user_id)
        if user == None:
            return None
            print("Never reached")
    except:
        return None
"""
    req = BugHuntRequest(
        repo_id="test-snippet-repo",
        code_snippet=buggy_code,
        target_path="user_service.py",
    )
    resp = await bug_agent_service.hunt_bugs(req, force_offline=True)

    assert resp.total_bugs >= 3
    assert len(resp.findings) >= 3
    assert "service.py" in resp.summary or "test-snippet-repo" in resp.summary
    assert resp.model_used == "ast-static-analyzer"


@pytest.mark.asyncio
async def test_workflow_graph_bug_hunting_execution():
    repo_id = "test-graph-bug-repo"
    buggy_chunk = CodeChunk(
        chunk_id="chk_bug_1",
        repo_id=repo_id,
        file_path="app/services/checkout.py",
        symbol_name="process_checkout",
        start_line=20,
        end_line=35,
        content="""def process_checkout(cart, discounts=[]):
    try:
        charge_card(cart)
    except:
        pass
""",
        token_count=15,
        metadata={"language": "python"},
    )
    hybrid_retriever_service.register_repo_chunks(repo_id, [buggy_chunk])

    graph = build_devmind_graph()
    initial_state = create_initial_state(
        repo_id=repo_id,
        user_query="Find bugs and crash hazards in the checkout service",
    )

    final_state = await graph.execute(initial_state)

    assert final_state["current_step"] == "completed"
    assert final_state["intent"] == "bug_hunt"
    assert len(final_state["diagnostic_findings"]) >= 1
    assert "app/services/checkout.py" in final_state["final_response"]
    assert len(final_state["citations"]) > 0
    assert final_state["metadata"]["total_bugs"] >= 1
