import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from fastapi import HTTPException, status

logger = logging.getLogger("devmind.guardrails")


class TokenBudgetExceededException(HTTPException):
    """Exception raised when an agent or repository exceeds its allocated token budget."""

    def __init__(self, detail: str, repo_id: str, current_usage: int, max_budget: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "token_budget_exceeded",
                "message": detail,
                "repo_id": repo_id,
                "current_usage": current_usage,
                "max_budget": max_budget,
            },
        )


class TokenGuardrailService:
    """Manages token accounting, cost computation, and budget enforcement across AI agent runs."""

    # Pricing per 1,000,000 tokens (USD)
    MODEL_RATES = {
        "gpt-4o": {"prompt": 5.00, "completion": 15.00},
        "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
        "text-embedding-3-small": {"prompt": 0.02, "completion": 0.00},
    }

    def __init__(
        self,
        default_max_tokens: int = 150_000,
        default_budget_cap_usd: float = 5.00,
        degradation_threshold: float = 0.80,
    ):
        self.default_max_tokens = default_max_tokens
        self.default_budget_cap_usd = default_budget_cap_usd
        self.degradation_threshold = degradation_threshold
        # {repo_id: {"prompt_tokens": int, "completion_tokens": int, "total_cost_usd": float, "requests_count": int, "last_updated": str}}
        self._usage_store: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def _get_or_create_account(self, repo_id: str) -> Dict[str, Any]:
        if repo_id not in self._usage_store:
            self._usage_store[repo_id] = {
                "repo_id": repo_id,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "requests_count": 0,
                "max_tokens_budget": self.default_max_tokens,
                "budget_cap_usd": self.default_budget_cap_usd,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        return self._usage_store[repo_id]

    def calculate_cost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Compute estimated USD cost based on published model token rates."""
        rates = self.MODEL_RATES.get(
            model, {"prompt": 5.00, "completion": 15.00}
        )
        prompt_cost = (prompt_tokens / 1_000_000) * rates["prompt"]
        completion_cost = (completion_tokens / 1_000_000) * rates["completion"]
        return round(prompt_cost + completion_cost, 6)

    def check_allowance(self, repo_id: str, estimated_tokens: int = 2000) -> Dict[str, Any]:
        """Verify repository has sufficient remaining quota before executing agent workflow.

        Raises TokenBudgetExceededException if budget or token caps are breached.
        """
        account = self._get_or_create_account(repo_id)
        current_tokens = account["total_tokens"]
        budget_limit = account["max_tokens_budget"]
        current_cost = account["total_cost_usd"]
        budget_cap_usd = account["budget_cap_usd"]

        # Check hard token budget cap
        if (current_tokens + estimated_tokens) > budget_limit:
            raise TokenBudgetExceededException(
                detail=f"Token allowance exceeded for repo '{repo_id}'. Current: {current_tokens}, Limit: {budget_limit}",
                repo_id=repo_id,
                current_usage=current_tokens,
                max_budget=budget_limit,
            )

        # Check hard USD spending cap
        if current_cost >= budget_cap_usd:
            raise TokenBudgetExceededException(
                detail=f"Spending cap of ${budget_cap_usd:.2f} reached for repo '{repo_id}'.",
                repo_id=repo_id,
                current_usage=current_tokens,
                max_budget=budget_limit,
            )

        # Check graceful degradation warning (usage > 80%)
        ratio = current_tokens / budget_limit if budget_limit > 0 else 0.0
        degradation_active = ratio >= self.degradation_threshold

        return {
            "allowed": True,
            "current_tokens": current_tokens,
            "budget_limit": budget_limit,
            "utilization_pct": round(ratio * 100, 2),
            "degradation_active": degradation_active,
        }

    def record_consumption(
        self,
        repo_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Dict[str, Any]:
        """Record token consumption and update cumulative spend for the repository."""
        account = self._get_or_create_account(repo_id)
        added_cost = self.calculate_cost(model, prompt_tokens, completion_tokens)

        account["prompt_tokens"] += prompt_tokens
        account["completion_tokens"] += completion_tokens
        account["total_tokens"] = account["prompt_tokens"] + account["completion_tokens"]
        account["total_cost_usd"] = round(account["total_cost_usd"] + added_cost, 6)
        account["requests_count"] += 1
        account["last_updated"] = datetime.now(timezone.utc).isoformat()

        logger.debug(
            f"Recorded {prompt_tokens + completion_tokens} tokens for {repo_id} ({model}). Total: {account['total_tokens']}"
        )
        return account

    def get_usage(self, repo_id: str) -> Dict[str, Any]:
        """Retrieve current usage statistics, remaining budget, and degradation status."""
        account = self._get_or_create_account(repo_id)
        budget_limit = account["max_tokens_budget"]
        remaining_tokens = max(0, budget_limit - account["total_tokens"])
        remaining_usd = max(0.0, round(account["budget_cap_usd"] - account["total_cost_usd"], 4))
        utilization_pct = (
            round((account["total_tokens"] / budget_limit) * 100, 2)
            if budget_limit > 0
            else 0.0
        )

        return {
            **account,
            "remaining_tokens": remaining_tokens,
            "remaining_usd": remaining_usd,
            "utilization_pct": utilization_pct,
            "degradation_active": utilization_pct >= (self.degradation_threshold * 100),
        }

    def reset_usage(self, repo_id: str) -> None:
        """Reset token consumption counter and spend for a repository."""
        if repo_id in self._usage_store:
            del self._usage_store[repo_id]


# Global Token Guardrail Singleton
token_guardrail = TokenGuardrailService()
