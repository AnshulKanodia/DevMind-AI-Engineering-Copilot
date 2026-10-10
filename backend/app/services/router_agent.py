import json
import re
from typing import List, Optional
import httpx

from app.agents.state import AgentIntent
from app.core.config import get_settings
from app.schemas.router import RouterClassificationResult

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

ROUTER_SYSTEM_PROMPT = """You are the DevMind Chief Architecture Router.
Analyze the developer query and classify the primary technical intent into exactly one of:
- code_qa: Natural language questions about code logic, data flow, architecture, or where features are implemented.
- bug_hunt: Inquiries about crashes, null errors, exceptions, anti-patterns, or fixing broken functionality.
- security_audit: Security questions, vulnerabilities (SQLi, XSS, CSRF, insecure hashing, hardcoded secrets, OWASP).
- test_gen: Requests to generate unit tests, test suites, mocks, fixtures, or edge-case tests (pytest, jest).
- doc_gen: Requests to generate or update READMEs, docstrings, architectural diagrams, or module summaries.
- pr_review: Requests to review git diffs, pull requests, patch changes, or assess breaking changes.

Return your answer strictly as a JSON object matching this schema:
{
  "intent": "code_qa" | "bug_hunt" | "security_audit" | "test_gen" | "doc_gen" | "pr_review",
  "confidence": float between 0.0 and 1.0,
  "reasoning": "brief explanation",
  "extracted_keywords": ["keyword1", "keyword2"],
  "target_subagent": "Code Q&A Agent" | "Bug Detection Agent" | "Security Audit Agent" | "Test Generation Agent" | "Documentation Agent" | "PR Review Agent",
  "suggested_search_queries": ["query1", "query2"]
}
"""


class RouterAgentService:
    """Intelligent query routing agent using LLM reasoning and heuristic fast paths."""

    def __init__(self):
        self.settings = get_settings()

    def _rule_based_fallback(self, query: str) -> RouterClassificationResult:
        """Heuristic classifier providing deterministic low-latency routing without API calls."""
        q = query.lower()
        words = re.findall(r"[a-zA-Z0-9_]+", q)

        if any(k in q for k in ["bug", "defect", "error", "broken", "issue", "crash", "fails", "exception"]):
            return RouterClassificationResult(
                intent=AgentIntent.BUG_HUNT,
                confidence=0.92,
                reasoning="Query contains defect or failure indicators requiring static review and bug diagnosis.",
                extracted_keywords=[w for w in words if len(w) > 3][:5],
                target_subagent="Bug Detection Agent",
                suggested_search_queries=[query, "error handling", "exception"],
            )
        elif any(k in q for k in ["security", "sqli", "injection", "vulnerability", "cve", "owasp", "sanitize", "xss", "csrf", "secret"]):
            return RouterClassificationResult(
                intent=AgentIntent.SECURITY_AUDIT,
                confidence=0.95,
                reasoning="Security or vulnerability keyword detected; routing to SAST & Security Auditor.",
                extracted_keywords=[w for w in words if len(w) > 3][:5],
                target_subagent="Security Audit Agent",
                suggested_search_queries=[query, "sanitize", "validate", "query"],
            )
        elif any(k in q for k in ["test", "unit test", "jest", "pytest", "mock", "assert", "coverage", "spec"]):
            return RouterClassificationResult(
                intent=AgentIntent.TEST_GEN,
                confidence=0.94,
                reasoning="Request for test synthesis and test case generation.",
                extracted_keywords=[w for w in words if len(w) > 3][:5],
                target_subagent="Test Generation Agent",
                suggested_search_queries=[query, "def ", "class "],
            )
        elif any(k in q for k in ["doc", "document", "readme", "comment", "architecture", "diagram", "explain overview"]):
            return RouterClassificationResult(
                intent=AgentIntent.DOC_GEN,
                confidence=0.90,
                reasoning="Documentation or architecture explanation request.",
                extracted_keywords=[w for w in words if len(w) > 3][:5],
                target_subagent="Documentation Agent",
                suggested_search_queries=[query, "overview", "main"],
            )
        elif any(k in q for k in ["pr", "pull request", "diff", "review change", "patch", "git diff"]):
            return RouterClassificationResult(
                intent=AgentIntent.PR_REVIEW,
                confidence=0.91,
                reasoning="Git pull request or diff inspection requested.",
                extracted_keywords=[w for w in words if len(w) > 3][:5],
                target_subagent="PR Review Agent",
                suggested_search_queries=[query, "diff"],
            )
        else:
            return RouterClassificationResult(
                intent=AgentIntent.CODE_QA,
                confidence=0.88,
                reasoning="Standard codebase inquiry; routing to grounded Code Q&A with vector search.",
                extracted_keywords=[w for w in words if len(w) > 3][:5],
                target_subagent="Code Q&A Agent",
                suggested_search_queries=[query],
            )

    async def classify_query(self, query: str, force_offline: bool = False) -> RouterClassificationResult:
        """Classify user query using OpenAI structured outputs with automatic fallback."""
        is_mock = (
            force_offline
            or not self.settings.OPENAI_API_KEY
            or self.settings.OPENAI_API_KEY.startswith("sk-placeholder")
        )

        if is_mock:
            return self._rule_based_fallback(query)

        # Online LLM classification
        headers = {
            "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.OPENAI_MINI_MODEL,
            "messages": [
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Developer query:\n{query}"},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(OPENAI_CHAT_URL, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                intent_val = parsed.get("intent", "code_qa")
                try:
                    intent_enum = AgentIntent(intent_val)
                except ValueError:
                    intent_enum = AgentIntent.CODE_QA

                return RouterClassificationResult(
                    intent=intent_enum,
                    confidence=float(parsed.get("confidence", 0.9)),
                    reasoning=parsed.get("reasoning", "Classified by Router Agent LLM"),
                    extracted_keywords=parsed.get("extracted_keywords", []),
                    target_subagent=parsed.get("target_subagent", "Code Q&A Agent"),
                    suggested_search_queries=parsed.get("suggested_search_queries", [query]),
                )
        except Exception:
            pass

        # Fallback if API fails or network timeout
        return self._rule_based_fallback(query)


router_agent_service = RouterAgentService()
