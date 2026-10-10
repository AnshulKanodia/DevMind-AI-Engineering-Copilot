import pytest
from app.agents.state import AgentIntent
from app.services.router_agent import router_agent_service


@pytest.mark.asyncio
async def test_router_agent_code_qa_routing():
    query = "How is user password hashing implemented in the codebase?"
    res = await router_agent_service.classify_query(query, force_offline=True)

    assert res.intent == AgentIntent.CODE_QA
    assert res.target_subagent == "Code Q&A Agent"
    assert res.confidence >= 0.8
    assert len(res.suggested_search_queries) > 0


@pytest.mark.asyncio
async def test_router_agent_bug_hunt_routing():
    query = "Why does the checkout service crash with an unexpected null pointer error?"
    res = await router_agent_service.classify_query(query, force_offline=True)

    assert res.intent == AgentIntent.BUG_HUNT
    assert res.target_subagent == "Bug Detection Agent"
    assert any("error" in q.lower() for q in res.suggested_search_queries) or "defect" in res.reasoning.lower()


@pytest.mark.asyncio
async def test_router_agent_security_audit_routing():
    query = "Audit this endpoint for potential SQLi vulnerabilities and unsanitized parameters"
    res = await router_agent_service.classify_query(query, force_offline=True)

    assert res.intent == AgentIntent.SECURITY_AUDIT
    assert res.target_subagent == "Security Audit Agent"
    assert res.confidence >= 0.9


@pytest.mark.asyncio
async def test_router_agent_test_generation_routing():
    query = "Generate pytest unit test cases for the calculateInterest method"
    res = await router_agent_service.classify_query(query, force_offline=True)

    assert res.intent == AgentIntent.TEST_GEN
    assert res.target_subagent == "Test Generation Agent"


@pytest.mark.asyncio
async def test_router_agent_doc_generation_routing():
    query = "Write a comprehensive README architecture summary and flow diagram"
    res = await router_agent_service.classify_query(query, force_offline=True)

    assert res.intent == AgentIntent.DOC_GEN
    assert res.target_subagent == "Documentation Agent"


@pytest.mark.asyncio
async def test_router_agent_pr_review_routing():
    query = "Review this git diff patch and find any breaking changes"
    res = await router_agent_service.classify_query(query, force_offline=True)

    assert res.intent == AgentIntent.PR_REVIEW
    assert res.target_subagent == "PR Review Agent"
