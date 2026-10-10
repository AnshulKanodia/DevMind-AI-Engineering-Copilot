import pytest
from app.agents.state import AgentIntent, create_initial_state
from app.agents.graph import build_devmind_graph, router_node, format_node


def test_create_initial_state():
    state = create_initial_state(repo_id="test-repo", user_query="How does auth work?")

    assert state["repo_id"] == "test-repo"
    assert state["user_query"] == "How does auth work?"
    assert state["intent"] == AgentIntent.UNKNOWN.value
    assert state["current_step"] == "initialized"
    assert state["iteration_count"] == 0
    assert len(state["messages"]) == 1


@pytest.mark.asyncio
async def test_router_node_intent_classification():
    # Test bug detection intent
    bug_state = create_initial_state(repo_id="r1", user_query="Why is the payment function throwing a null error bug?")
    routed_bug = await router_node(bug_state)
    assert routed_bug["intent"] == AgentIntent.BUG_HUNT.value

    # Test security audit intent
    sec_state = create_initial_state(repo_id="r1", user_query="Scan the repository for SQLi and vulnerabilities")
    routed_sec = await router_node(sec_state)
    assert routed_sec["intent"] == AgentIntent.SECURITY_AUDIT.value

    # Test unit test generation intent
    test_state = create_initial_state(repo_id="r1", user_query="Generate pytest unit tests with mock assertions")
    routed_test = await router_node(test_state)
    assert routed_test["intent"] == AgentIntent.TEST_GEN.value

    # Test documentation generation intent
    doc_state = create_initial_state(repo_id="r1", user_query="Generate architecture documentation and README diagram")
    routed_doc = await router_node(doc_state)
    assert routed_doc["intent"] == AgentIntent.DOC_GEN.value

    # Test PR review intent
    pr_state = create_initial_state(repo_id="r1", user_query="Review the git diff in this PR")
    routed_pr = await router_node(pr_state)
    assert routed_pr["intent"] == AgentIntent.PR_REVIEW.value

    # Test standard Code Q&A
    qa_state = create_initial_state(repo_id="r1", user_query="Where is the database connection initialized?")
    routed_qa = await router_node(qa_state)
    assert routed_qa["intent"] == AgentIntent.CODE_QA.value


@pytest.mark.asyncio
async def test_format_node_appends_citations():
    state = create_initial_state(repo_id="r1", user_query="How does JWT work?")
    state["final_response"] = "JWT authentication uses the secret from config."
    state["citations"] = ["auth.py:45-52", "config.py:12-15"]

    formatted = await format_node(state)
    assert formatted["current_step"] == "formatting_output"
    assert "auth.py:45-52" in formatted["final_response"]
    assert "config.py:12-15" in formatted["final_response"]


@pytest.mark.asyncio
async def test_workflow_graph_end_to_end_execution():
    graph = build_devmind_graph()
    state = create_initial_state(repo_id="r1", user_query="Generate unit test for calculate_tax")

    final_state = await graph.execute(state)

    assert final_state["current_step"] == "completed"
    assert final_state["intent"] == AgentIntent.TEST_GEN.value
    assert final_state["iteration_count"] == 1
