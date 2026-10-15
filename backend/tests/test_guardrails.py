import pytest
from fastapi.testclient import TestClient

from app.core.guardrails import (
    TokenBudgetExceededException,
    TokenGuardrailService,
    token_guardrail,
)
from app.core.rate_limiter import SlidingWindowRateLimiter, rate_limiter
from app.main import app


@pytest.fixture(autouse=True)
def reset_all_guardrails():
    """Reset rate limiter and token store between tests."""
    token_guardrail.reset_usage("test-repo")
    token_guardrail.reset_usage("budget-capped-repo")
    rate_limiter.reset()
    yield
    token_guardrail.reset_usage("test-repo")
    token_guardrail.reset_usage("budget-capped-repo")
    rate_limiter.reset()


def test_calculate_cost():
    """Verify cost calculation across different OpenAI models."""
    guardrail = TokenGuardrailService()
    # 1,000,000 prompt tokens of gpt-4o = $5.00, 1,000,000 completion = $15.00
    cost_gpt4o = guardrail.calculate_cost("gpt-4o", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost_gpt4o == 20.0

    # 1,000,000 prompt tokens of gpt-4o-mini = $0.15, 1,000,000 completion = $0.60
    cost_mini = guardrail.calculate_cost("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert cost_mini == 0.75


def test_record_consumption_accumulates():
    """Verify token usage and USD spend accumulate accurately."""
    guardrail = TokenGuardrailService()
    guardrail.record_consumption("repo-1", "gpt-4o", prompt_tokens=1000, completion_tokens=500)
    guardrail.record_consumption("repo-1", "gpt-4o", prompt_tokens=2000, completion_tokens=1000)

    usage = guardrail.get_usage("repo-1")
    assert usage["prompt_tokens"] == 3000
    assert usage["completion_tokens"] == 1500
    assert usage["total_tokens"] == 4500
    assert usage["requests_count"] == 2
    assert usage["total_cost_usd"] > 0.0


def test_check_allowance_degradation_threshold():
    """Verify degradation_active flag turns True once consumption crosses 80% threshold."""
    guardrail = TokenGuardrailService(default_max_tokens=10_000)
    # Record 8,500 tokens (85% utilization)
    guardrail.record_consumption("repo-degrade", "gpt-4o", prompt_tokens=5000, completion_tokens=3500)

    allowance = guardrail.check_allowance("repo-degrade", estimated_tokens=100)
    assert allowance["allowed"] is True
    assert allowance["degradation_active"] is True
    assert allowance["utilization_pct"] == 85.0


def test_check_allowance_raises_token_budget_exceeded():
    """Verify TokenBudgetExceededException is raised when budget is exceeded."""
    guardrail = TokenGuardrailService(default_max_tokens=5000)
    guardrail.record_consumption("repo-exhausted", "gpt-4o", prompt_tokens=3000, completion_tokens=2000)

    with pytest.raises(TokenBudgetExceededException) as excinfo:
        guardrail.check_allowance("repo-exhausted", estimated_tokens=500)

    assert excinfo.value.status_code == 429
    assert excinfo.value.detail["error"] == "token_budget_exceeded"
    assert excinfo.value.detail["repo_id"] == "repo-exhausted"


def test_check_allowance_raises_usd_spending_cap():
    """Verify TokenBudgetExceededException is raised when USD spending cap is exceeded."""
    guardrail = TokenGuardrailService(default_max_tokens=1_000_000, default_budget_cap_usd=0.01)
    # Record enough tokens to exceed $0.01
    guardrail.record_consumption("repo-expensive", "gpt-4o", prompt_tokens=2000, completion_tokens=1000)

    with pytest.raises(TokenBudgetExceededException):
        guardrail.check_allowance("repo-expensive", estimated_tokens=100)


def test_sliding_window_rate_limiter():
    """Verify SlidingWindowRateLimiter permits up to limit then enforces cooldown."""
    limiter = SlidingWindowRateLimiter(default_limit=5, window_seconds=60)
    client_id = "test-client-127.0.0.1"

    for _ in range(5):
        allowed, remaining, _ = limiter.is_allowed(client_id)
        assert allowed is True

    # 6th request should be blocked
    allowed, remaining, retry_after = limiter.is_allowed(client_id)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


def test_guardrails_api_usage_and_reset():
    """Verify GET /api/v1/guardrails/usage and POST /api/v1/guardrails/reset."""
    client = TestClient(app)
    token_guardrail.record_consumption("test-repo", "gpt-4o", prompt_tokens=500, completion_tokens=200)

    resp = client.get("/api/v1/guardrails/usage/test-repo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tokens"] == 700
    assert data["remaining_tokens"] > 0

    reset_resp = client.post("/api/v1/guardrails/reset/test-repo")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "reset"

    usage_after = client.get("/api/v1/guardrails/usage/test-repo").json()
    assert usage_after["total_tokens"] == 0


def test_rate_limiting_middleware_enforces_429():
    """Verify HTTP requests past client quota trigger 429 Too Many Requests with Retry-After header."""
    client = TestClient(app)
    test_limiter = rate_limiter
    original_limit = test_limiter.default_limit
    test_limiter.default_limit = 3

    try:
        # First 3 requests succeed
        for _ in range(3):
            r = client.get("/api/v1/repos")
            assert r.status_code in [200, 404]

        # 4th request must be blocked by rate limiter
        blocked = client.get("/api/v1/repos")
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers
        assert "Rate limit exceeded" in blocked.json()["detail"]
    finally:
        test_limiter.default_limit = original_limit


def test_exempt_endpoints_bypass_rate_limiting():
    """Verify /health and /metrics bypass rate limiter even when quota is exhausted."""
    client = TestClient(app)
    test_limiter = rate_limiter
    original_limit = test_limiter.default_limit
    test_limiter.default_limit = 1

    try:
        # Exhaust quota on standard endpoint
        client.get("/api/v1/repos")
        blocked = client.get("/api/v1/repos")
        assert blocked.status_code == 429

        # Health and metrics remain operational
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        metrics_resp = client.get("/metrics")
        assert metrics_resp.status_code == 200
    finally:
        test_limiter.default_limit = original_limit
