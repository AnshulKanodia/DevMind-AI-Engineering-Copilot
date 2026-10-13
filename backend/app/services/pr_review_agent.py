import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import get_settings
from app.schemas.github import GitHubInlineReviewComment, GitHubPullRequestDiff
from app.schemas.pr_review import (
    PRReviewFinding,
    PRReviewIssueCategory,
    PRReviewRequest,
    PRReviewResponse,
    PRReviewSeverity,
    PRReviewVerdict,
)
from app.services.github_client import github_client_service
from app.services.secrets_sanitizer import secrets_sanitizer_service

logger = logging.getLogger("devmind.agents.pr_review")

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

PR_REVIEW_SYSTEM_PROMPT = """You are the DevMind Staff Principal Code Reviewer and Tech Lead.
Analyze the provided GitHub Pull Request unified diff for regressions, architectural anti-patterns,
security vulnerabilities (OWASP/CWE), runtime crashes, and missing test coverage.

Return your response strictly as a JSON object matching this schema:
{
  "verdict": "APPROVE" | "COMMENT" | "REQUEST_CHANGES",
  "summary": "High-level review summary evaluating code quality, risks, and test coverage",
  "findings": [
    {
      "file_path": "path/to/file",
      "line_number": 15,
      "category": "security" | "bug_risk" | "breaking_change" | "missing_tests" | "style_standards",
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "title": "Concise issue headline",
      "description": "Technical analysis of why this diff introduces risk",
      "suggested_patch": "Recommended replacement code or diff hunk",
      "confidence": 0.95
    }
  ]
}
"""


class PRReviewAgentService:
    """Specialized agent service for analyzing Git pull request diffs, detecting regressions, and generating review comments."""

    def __init__(self):
        self.settings = get_settings()

    def parse_raw_diff(self, raw_diff: str) -> List[Tuple[str, List[Tuple[int, str]]]]:
        """Parse a unified git diff into file paths and (line_number, added_code_line) pairs."""
        files: List[Tuple[str, List[Tuple[int, str]]]] = []
        current_file: Optional[str] = None
        current_lines: List[Tuple[int, str]] = []
        current_new_line = 0

        for line in raw_diff.splitlines():
            if line.startswith("diff --git"):
                if current_file and current_lines:
                    files.append((current_file, current_lines))
                # diff --git a/path b/path
                parts = line.split(" b/")
                current_file = parts[1].strip() if len(parts) > 1 else "unknown"
                current_lines = []
                current_new_line = 0
            elif line.startswith("+++ b/"):
                current_file = line.replace("+++ b/", "").strip()
            elif line.startswith("@@"):
                # @@ -old,count +new,count @@
                match = re.search(r"\+(\d+)(?:,\d+)?", line)
                if match:
                    current_new_line = int(match.group(1))
            elif line.startswith("+") and not line.startswith("+++"):
                added_code = line[1:]
                if current_file:
                    current_lines.append((current_new_line, added_code))
                current_new_line += 1
            elif not line.startswith("-"):
                current_new_line += 1

        if current_file and current_lines:
            files.append((current_file, current_lines))

        return files

    def analyze_diff_hunks(
        self, files: List[Tuple[str, List[Tuple[int, str]]]]
    ) -> List[PRReviewFinding]:
        """Perform static analysis on added lines in PR diff to detect security and defect regressions."""
        findings: List[PRReviewFinding] = []
        has_test_files = any(
            "test" in fname.lower() or "spec" in fname.lower()
            for fname, _ in files
        )
        total_code_additions = sum(len(lines) for _, lines in files)

        for fname, added_lines in files:
            is_py = fname.endswith((".py", ".pyw"))
            is_ts = fname.endswith((".ts", ".tsx", ".js", ".jsx"))

            for lineno, code in added_lines:
                stripped = code.strip()

                # 1. Security: SQL Injection via f-string or string formatting
                if re.search(r'(?:SELECT|INSERT|UPDATE|DELETE)\s+.*\{[a-zA-Z0-9_]+\}', stripped, re.IGNORECASE) or (
                    any(k in stripped.upper() for k in ("SELECT ", "INSERT ", "UPDATE ", "DELETE "))
                    and ('f"' in stripped or "f'" in stripped or "%" in stripped)
                ):
                    findings.append(
                        PRReviewFinding(
                            file_path=fname,
                            line_number=lineno,
                            category=PRReviewIssueCategory.SECURITY,
                            severity=PRReviewSeverity.CRITICAL,
                            title="SQL Injection hazard in PR diff",
                            description="Newly introduced SQL query uses string interpolation instead of parameterized placeholders.",
                            suggested_patch="cursor.execute('SELECT ... WHERE id = ?', (user_id,))",
                            confidence=0.98,
                        )
                    )

                # 2. Security: OS Command Injection / eval / exec
                if "os.system(" in stripped or ("subprocess" in stripped and "shell=True" in stripped):
                    findings.append(
                        PRReviewFinding(
                            file_path=fname,
                            line_number=lineno,
                            category=PRReviewIssueCategory.SECURITY,
                            severity=PRReviewSeverity.CRITICAL,
                            title="Command Injection via shell execution",
                            description="Command executes in shell mode (`shell=True` or `os.system`), exposing server to arbitrary command execution.",
                            suggested_patch="subprocess.run(['command', arg], shell=False, check=True)",
                            confidence=0.97,
                        )
                    )
                if is_py and re.search(r"\b(?:eval|exec)\s*\(", stripped):
                    findings.append(
                        PRReviewFinding(
                            file_path=fname,
                            line_number=lineno,
                            category=PRReviewIssueCategory.SECURITY,
                            severity=PRReviewSeverity.CRITICAL,
                            title="Dynamic code execution hazard",
                            description="Dynamic code execution allows arbitrary code evaluation if inputs contain untrusted data.",
                            suggested_patch="ast.literal_eval(payload) or json.loads(payload)",
                            confidence=0.99,
                        )
                    )

                # 3. Security: Insecure Deserialization
                if is_py and "pickle.loads(" in stripped:
                    findings.append(
                        PRReviewFinding(
                            file_path=fname,
                            line_number=lineno,
                            category=PRReviewIssueCategory.SECURITY,
                            severity=PRReviewSeverity.CRITICAL,
                            title="Insecure pickle deserialization",
                            description="Deserializing untrusted byte streams with pickle allows remote code execution.",
                            suggested_patch="json.loads(payload) or msgpack.unpackb(payload)",
                            confidence=0.98,
                        )
                    )

                # 4. Security: Weak Cryptographic Hash
                if is_py and re.search(r"hashlib\.(?:md5|sha1)\s*\(", stripped):
                    findings.append(
                        PRReviewFinding(
                            file_path=fname,
                            line_number=lineno,
                            category=PRReviewIssueCategory.SECURITY,
                            severity=PRReviewSeverity.HIGH,
                            title="Weak cryptographic hashing algorithm",
                            description="MD5 and SHA-1 algorithms are cryptographically broken and vulnerable to hash collision attacks.",
                            suggested_patch="hashlib.sha256(data).hexdigest()",
                            confidence=0.95,
                        )
                    )

                # 5. Security: Hardcoded Credentials
                for sec_type, pat in secrets_sanitizer_service.KNOWN_SECRET_PATTERNS.items():
                    if sec_type == "generic_api_assignment":
                        continue
                    if pat.search(stripped):
                        findings.append(
                            PRReviewFinding(
                                file_path=fname,
                                line_number=lineno,
                                category=PRReviewIssueCategory.SECURITY,
                                severity=PRReviewSeverity.HIGH,
                                title=f"Hardcoded credential ({sec_type}) in PR diff",
                                description=f"Potential credential or secret key committed directly in pull request diff.",
                                suggested_patch="os.environ.get('API_SECRET_KEY')",
                                confidence=0.96,
                            )
                        )

                # 6. Security: Frontend XSS / dangerouslySetInnerHTML
                if is_ts and ("dangerouslySetInnerHTML" in stripped or ".innerHTML" in stripped):
                    findings.append(
                        PRReviewFinding(
                            file_path=fname,
                            line_number=lineno,
                            category=PRReviewIssueCategory.SECURITY,
                            severity=PRReviewSeverity.HIGH,
                            title="DOM XSS risk in frontend component",
                            description="Direct assignment to innerHTML or dangerouslySetInnerHTML exposes users to cross-site scripting attacks.",
                            suggested_patch="Sanitize with DOMPurify.sanitize(html) before rendering.",
                            confidence=0.92,
                        )
                    )

                # 7. Bug Risk: Mutable default arguments in Python
                if is_py and re.search(r"def\s+[a-zA-Z0-9_]+\s*\(.*=\s*(\[\]|\{\}|\bset\(\))", stripped):
                    findings.append(
                        PRReviewFinding(
                            file_path=fname,
                            line_number=lineno,
                            category=PRReviewIssueCategory.BUG_RISK,
                            severity=PRReviewSeverity.MEDIUM,
                            title="Mutable default parameter anti-pattern",
                            description="Mutable default parameter is evaluated once at function definition time, leaking state between invocations.",
                            suggested_patch="param=None; if param is None: param = []",
                            confidence=0.95,
                        )
                    )

                # 8. Bug Risk: Bare except clause
                if is_py and re.search(r"except\s*:\s*$", stripped):
                    findings.append(
                        PRReviewFinding(
                            file_path=fname,
                            line_number=lineno,
                            category=PRReviewIssueCategory.BUG_RISK,
                            severity=PRReviewSeverity.MEDIUM,
                            title="Bare except clause intercepts process signals",
                            description="A bare `except:` intercepts SystemExit and KeyboardInterrupt, obscuring unhandled errors.",
                            suggested_patch="except Exception as exc: logger.error(f'Error: {exc}')",
                            confidence=0.96,
                        )
                    )

                # 9. Bug Risk: Comparison to None using ==
                if is_py and re.search(r"\b(?:==|!=)\s*None\b", stripped):
                    findings.append(
                        PRReviewFinding(
                            file_path=fname,
                            line_number=lineno,
                            category=PRReviewIssueCategory.STYLE_STANDARDS,
                            severity=PRReviewSeverity.LOW,
                            title="Non-idiomatic equality comparison to None",
                            description="Comparisons to None should use the identity operators `is None` or `is not None`.",
                            suggested_patch="if val is None:",
                            confidence=0.92,
                        )
                    )

        # 10. Missing Tests check: substantial additions (>15 lines) without test files
        if total_code_additions >= 15 and not has_test_files and files:
            first_fname = files[0][0]
            findings.append(
                PRReviewFinding(
                    file_path=first_fname,
                    line_number=1,
                    category=PRReviewIssueCategory.MISSING_TESTS,
                    severity=PRReviewSeverity.MEDIUM,
                    title="PR lacks automated unit test coverage",
                    description=f"Pull request adds {total_code_additions} lines of logic across {len(files)} files without accompanying unit test suites.",
                    suggested_patch=f"Add unit tests in tests/test_{first_fname.split('/')[-1]}",
                    confidence=0.90,
                )
            )

        # De-duplicate findings by (file_path, line_number, title)
        seen = set()
        deduped: List[PRReviewFinding] = []
        for f in findings:
            key = (f.file_path, f.line_number, f.title)
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        return deduped

    def compute_verdict(self, findings: List[PRReviewFinding]) -> PRReviewVerdict:
        """Calculate overall PR review decision based on finding severities."""
        has_critical = any(
            f.severity in (PRReviewSeverity.CRITICAL, PRReviewSeverity.HIGH)
            for f in findings
        )
        has_medium = any(f.severity == PRReviewSeverity.MEDIUM for f in findings)

        if has_critical:
            return PRReviewVerdict.REQUEST_CHANGES
        elif has_medium or len(findings) > 0:
            return PRReviewVerdict.COMMENT
        return PRReviewVerdict.APPROVE

    def generate_inline_comments(
        self, findings: List[PRReviewFinding]
    ) -> List[GitHubInlineReviewComment]:
        """Convert PR review findings into GitHub inline review comment objects."""
        comments: List[GitHubInlineReviewComment] = []
        for f in findings:
            body_parts = [
                f"**[{f.category.value.upper()} • {f.severity.value.upper()}] {f.title}**\n",
                f"{f.description}\n",
            ]
            if f.suggested_patch:
                body_parts.append(f"```suggestion\n{f.suggested_patch}\n```")
            comments.append(
                GitHubInlineReviewComment(
                    path=f.file_path,
                    line=f.line_number,
                    side="RIGHT",
                    body="\n".join(body_parts),
                )
            )
        return comments

    def format_summary(
        self,
        repo_id: str,
        pr_number: Optional[int],
        verdict: PRReviewVerdict,
        findings: List[PRReviewFinding],
        files_reviewed: List[str],
        total_adds: int,
        total_dels: int,
    ) -> str:
        """Render a formatted Markdown review summary."""
        pr_label = f"#{pr_number}" if pr_number else "Diff"
        verdict_badge = {
            PRReviewVerdict.APPROVE: " **APPROVED**",
            PRReviewVerdict.COMMENT: " **COMMENTED**",
            PRReviewVerdict.REQUEST_CHANGES: " **CHANGES REQUESTED**",
        }.get(verdict, verdict.value)

        lines = [
            f"### DevMind Pull Request Review: `{repo_id}` ({pr_label})",
            f"**Verdict:** {verdict_badge}",
            f"**Diff Metrics:** {len(files_reviewed)} files reviewed (+{total_adds} / -{total_dels} lines)\n",
        ]

        if not findings:
            lines.append(" **No regressions or security hazards detected.**")
            lines.append("The proposed changes adhere to architectural standards and safety best practices.")
            return "\n".join(lines)

        crits = sum(1 for f in findings if f.severity in (PRReviewSeverity.CRITICAL, PRReviewSeverity.HIGH))
        meds = sum(1 for f in findings if f.severity == PRReviewSeverity.MEDIUM)
        lows = sum(1 for f in findings if f.severity in (PRReviewSeverity.LOW, PRReviewSeverity.INFO))

        lines.append(f"**Total Issues Identified:** {len(findings)} (Critical/High: {crits}, Medium: {meds}, Low: {lows})\n")
        lines.append("| Severity | Category | Location | Issue Headline |")
        lines.append("| :--- | :--- | :--- | :--- |")

        for f in findings:
            loc = f"`{f.file_path}:{f.line_number}`"
            sev = f"**{f.severity.value.upper()}**"
            lines.append(f"| {sev} | `{f.category.value}` | {loc} | {f.title} |")

        lines.append("\n#### Detailed Findings & Suggested Inline Patches:\n")
        for idx, f in enumerate(findings, 1):
            lines.append(f"**{idx}. [{f.severity.value.upper()}] {f.title}** (`{f.file_path}:{f.line_number}`)")
            lines.append(f"- **Category:** `{f.category.value}`")
            lines.append(f"- **Analysis:** {f.description}")
            if f.suggested_patch:
                lines.append(f"- **Suggested Patch:**\n```python\n{f.suggested_patch}\n```\n")

        return "\n".join(lines)

    async def review_pull_request(
        self,
        request: PRReviewRequest,
        force_offline: bool = False,
    ) -> PRReviewResponse:
        """Execute automated PR review on git diff or GitHub pull request."""
        raw_diff = request.raw_diff or ""
        pr_number = request.pr_number
        files_reviewed: List[str] = []
        total_adds = 0
        total_dels = 0

        # 1. If PR number or full name provided without raw diff, fetch from GitHub API client
        if (pr_number or request.repo_full_name) and not raw_diff:
            repo_name = request.repo_full_name or request.repo_id
            num = pr_number or 1
            diff_obj: GitHubPullRequestDiff = await github_client_service.fetch_pull_request_diff(
                repo_full_name=repo_name,
                pr_number=num,
                token=request.github_token,
                force_offline=force_offline,
            )
            raw_diff = diff_obj.raw_diff
            pr_number = diff_obj.pr_number
            files_reviewed = [f.filename for f in diff_obj.files]
            total_adds = diff_obj.total_additions
            total_dels = diff_obj.total_deletions

        # 2. Parse diff hunks
        parsed_files = self.parse_raw_diff(raw_diff)
        if not files_reviewed:
            files_reviewed = [fname for fname, _ in parsed_files]
        if total_adds == 0:
            total_adds = sum(len(lines) for _, lines in parsed_files)

        # 3. Analyze diff for defects and security issues
        findings = self.analyze_diff_hunks(parsed_files)
        verdict = self.compute_verdict(findings)
        inline_comments = self.generate_inline_comments(findings)

        # 4. Optional online LLM enhancement
        is_mock = (
            force_offline
            or not self.settings.OPENAI_API_KEY
            or self.settings.OPENAI_API_KEY.startswith("sk-placeholder")
        )

        if not is_mock and raw_diff:
            headers = {
                "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.settings.OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": PR_REVIEW_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Repository: {request.repo_id}\nPR Number: {pr_number}\n"
                            f"Files: {', '.join(files_reviewed)}\nUnified Diff:\n{raw_diff[:8000]}"
                        ),
                    },
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }
            try:
                async with httpx.AsyncClient(timeout=25.0) as client:
                    resp = await client.post(OPENAI_CHAT_URL, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    parsed = json.loads(data["choices"][0]["message"]["content"])
                    llm_findings = [
                        PRReviewFinding(
                            file_path=f.get("file_path", files_reviewed[0] if files_reviewed else "code.py"),
                            line_number=int(f.get("line_number", 1)),
                            category=PRReviewIssueCategory(f.get("category", "bug_risk")),
                            severity=PRReviewSeverity(f.get("severity", "medium")),
                            title=f.get("title", "Review finding"),
                            description=f.get("description", ""),
                            suggested_patch=f.get("suggested_patch"),
                            confidence=float(f.get("confidence", 0.9)),
                        )
                        for f in parsed.get("findings", [])
                    ]
                    if llm_findings:
                        findings = llm_findings
                        verdict = PRReviewVerdict(parsed.get("verdict", verdict.value))
                        inline_comments = self.generate_inline_comments(findings)
                        summary = parsed.get("summary") or self.format_summary(
                            request.repo_id, pr_number, verdict, findings, files_reviewed, total_adds, total_dels
                        )
                        return PRReviewResponse(
                            repo_id=request.repo_id,
                            pr_number=pr_number,
                            verdict=verdict,
                            summary=summary,
                            findings=findings,
                            inline_comments=inline_comments,
                            files_reviewed=files_reviewed,
                            total_additions=total_adds,
                            total_deletions=total_dels,
                            model_used=self.settings.OPENAI_MODEL,
                        )
            except Exception as exc:
                logger.warning(f"LLM PR review failed: {exc}; using AST diff analyzer.")

        summary = self.format_summary(
            request.repo_id, pr_number, verdict, findings, files_reviewed, total_adds, total_dels
        )
        return PRReviewResponse(
            repo_id=request.repo_id,
            pr_number=pr_number,
            verdict=verdict,
            summary=summary,
            findings=findings,
            inline_comments=inline_comments,
            files_reviewed=files_reviewed,
            total_additions=total_adds,
            total_deletions=total_dels,
            model_used="pr-review-diff-analyzer",
        )


pr_review_agent_service = PRReviewAgentService()
