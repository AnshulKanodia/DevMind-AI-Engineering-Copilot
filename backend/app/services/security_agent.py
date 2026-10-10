import ast
import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings
from app.schemas.retrieval import HybridSearchQuery
from app.schemas.security import (
    OWASPCategory,
    SecurityAuditRequest,
    SecurityAuditResponse,
    SecurityVulnerability,
    VulnerabilitySeverity,
)
from app.services.hybrid_retriever import hybrid_retriever_service
from app.services.secrets_sanitizer import secrets_sanitizer_service

logger = logging.getLogger("devmind.agents.security")

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

SECURITY_AGENT_SYSTEM_PROMPT = """You are the DevMind Principal Application Security Engineer (AppSec & SAST).
Audit the provided code context for software vulnerabilities adhering strictly to OWASP Top 10 and CWE standards.

Detect:
- SQL Injection (CWE-89)
- Command Injection / Remote Code Execution (CWE-78, CWE-94)
- Broken Cryptography / Insecure Hashing (CWE-327, CWE-328)
- Hardcoded Secrets / Credentials (CWE-798)
- Insecure Deserialization (CWE-502)
- Cross-Site Scripting (XSS / CWE-79)
- Path Traversal (CWE-22)

Format your response as a JSON object matching this schema:
{
  "summary": "Executive security posture summary",
  "vulnerabilities": [
    {
      "rule_id": "SEC-XXX-001",
      "cwe_id": "CWE-XX",
      "owasp_category": "A0X:2021-...",
      "title": "Concise vulnerability title",
      "description": "Technical threat analysis and exploit mechanism",
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "file_path": "path/to/file",
      "line_number": 10,
      "end_line_number": 12,
      "code_snippet": "...",
      "remediation": "Prescriptive remediation guidance and patch",
      "confidence": 0.95
    }
  ]
}
"""


class PythonSecurityASTChecker(ast.NodeVisitor):
    """AST analyzer dedicated to security anti-patterns and vulnerabilities."""

    def __init__(self, file_path: str, lines: List[str]):
        self.file_path = file_path
        self.lines = lines
        self.vulnerabilities: List[SecurityVulnerability] = []

    def _get_snippet(self, start_line: int, end_line: int) -> str:
        s_idx = max(0, start_line - 1)
        e_idx = min(len(self.lines), end_line)
        return "".join(self.lines[s_idx:e_idx]).strip()

    def visit_Call(self, node: ast.Call):
        lineno = getattr(node, "lineno", 1)
        end_lineno = getattr(node, "end_lineno", lineno)

        # 1. Command Injection: eval(), exec()
        if isinstance(node.func, ast.Name):
            if node.func.id in ("eval", "exec"):
                self.vulnerabilities.append(
                    SecurityVulnerability(
                        rule_id="SEC-INJ-002",
                        cwe_id="CWE-94",
                        owasp_category=OWASPCategory.A03_INJECTION,
                        title=f"Dangerous dynamic code execution via `{node.func.id}()`",
                        description=(
                            f"Invoking `{node.func.id}()` with non-static expressions allows arbitrary code "
                            "execution and full server takeover if input is untrusted."
                        ),
                        severity=VulnerabilitySeverity.CRITICAL,
                        file_path=self.file_path,
                        line_number=lineno,
                        end_line_number=end_lineno,
                        code_snippet=self._get_snippet(lineno, end_lineno),
                        remediation="Avoid dynamic code execution. Refactor with static dispatch tables or safe parsing (e.g. `ast.literal_eval`).",
                        confidence=0.99,
                    )
                )

        # 2. Command Injection: os.system() or subprocess.run/Popen with shell=True
        if isinstance(node.func, ast.Attribute):
            # os.system(...)
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "system":
                self.vulnerabilities.append(
                    SecurityVulnerability(
                        rule_id="SEC-INJ-003",
                        cwe_id="CWE-78",
                        owasp_category=OWASPCategory.A03_INJECTION,
                        title="OS command execution via `os.system`",
                        description="`os.system()` passes commands directly to system shell without input escaping, leading to command injection.",
                        severity=VulnerabilitySeverity.CRITICAL,
                        file_path=self.file_path,
                        line_number=lineno,
                        end_line_number=end_lineno,
                        code_snippet=self._get_snippet(lineno, end_lineno),
                        remediation="Replace with `subprocess.run(args, shell=False)` passing arguments as an explicit list.",
                        confidence=0.98,
                    )
                )
            # subprocess(..., shell=True)
            elif (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and node.func.attr in ("Popen", "run", "call", "check_call", "check_output")
            ):
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        self.vulnerabilities.append(
                            SecurityVulnerability(
                                rule_id="SEC-INJ-003",
                                cwe_id="CWE-78",
                                owasp_category=OWASPCategory.A03_INJECTION,
                                title=f"`subprocess.{node.func.attr}` invoked with `shell=True`",
                                description="Executing subprocess calls through a shell enables shell metacharacter injection (;, |, &&).",
                                severity=VulnerabilitySeverity.HIGH,
                                file_path=self.file_path,
                                line_number=lineno,
                                end_line_number=end_lineno,
                                code_snippet=self._get_snippet(lineno, end_lineno),
                                remediation="Set `shell=False` and pass command and arguments as a sequence: `['command', 'arg1']`.",
                                confidence=0.96,
                            )
                        )

            # 3. Insecure Cryptographic Hash: hashlib.md5() or hashlib.sha1()
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "hashlib"
                and node.func.attr in ("md5", "sha1")
            ):
                self.vulnerabilities.append(
                    SecurityVulnerability(
                        rule_id="SEC-CRYPTO-001",
                        cwe_id="CWE-328",
                        owasp_category=OWASPCategory.A02_CRYPTOGRAPHIC_FAILURES,
                        title=f"Weak cryptographic hash algorithm `{node.func.attr}`",
                        description=f"Algorithm `{node.func.attr}` is cryptographically broken and vulnerable to collision attacks.",
                        severity=VulnerabilitySeverity.HIGH,
                        file_path=self.file_path,
                        line_number=lineno,
                        end_line_number=end_lineno,
                        code_snippet=self._get_snippet(lineno, end_lineno),
                        remediation="Upgrade to `hashlib.sha256()` or `hashlib.sha3_256()`. For passwords, use `argon2id` or `bcrypt`.",
                        confidence=0.95,
                    )
                )

            # 4. Insecure Deserialization: pickle.loads / pickle.load
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "pickle"
                and node.func.attr in ("loads", "load")
            ):
                self.vulnerabilities.append(
                    SecurityVulnerability(
                        rule_id="SEC-INTEG-001",
                        cwe_id="CWE-502",
                        owasp_category=OWASPCategory.A08_SOFTWARE_DATA_INTEGRITY,
                        title=f"Insecure deserialization via `pickle.{node.func.attr}`",
                        description="`pickle` can deserialize arbitrary Python objects, allowing attackers to trigger remote code execution upon loading.",
                        severity=VulnerabilitySeverity.CRITICAL,
                        file_path=self.file_path,
                        line_number=lineno,
                        end_line_number=end_lineno,
                        code_snippet=self._get_snippet(lineno, end_lineno),
                        remediation="Use secure serialization formats like JSON, Protobuf, or MsgPack instead of pickle.",
                        confidence=0.99,
                    )
                )

            # 5. SQL Injection via raw execute calls with string formatting
            if node.func.attr in ("execute", "executemany"):
                if node.args:
                    arg0 = node.args[0]
                    # Check if first arg is an f-string (JoinedStr) or BinOp % or Call .format()
                    is_interpolated = False
                    if isinstance(arg0, ast.JoinedStr):
                        is_interpolated = True
                    elif isinstance(arg0, ast.BinOp) and isinstance(arg0.op, ast.Mod):
                        is_interpolated = True
                    elif (
                        isinstance(arg0, ast.Call)
                        and isinstance(arg0.func, ast.Attribute)
                        and arg0.func.attr == "format"
                    ):
                        is_interpolated = True

                    if is_interpolated:
                        snippet = self._get_snippet(lineno, end_lineno)
                        if any(k in snippet.upper() for k in ("SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "FROM", "WHERE")):
                            self.vulnerabilities.append(
                                SecurityVulnerability(
                                    rule_id="SEC-INJ-001",
                                    cwe_id="CWE-89",
                                    owasp_category=OWASPCategory.A03_INJECTION,
                                    title="SQL Injection via string interpolation in database query",
                                    description="Constructing SQL queries via string formatting or f-strings allows arbitrary SQL injection attacks.",
                                    severity=VulnerabilitySeverity.CRITICAL,
                                    file_path=self.file_path,
                                    line_number=lineno,
                                    end_line_number=end_lineno,
                                    code_snippet=snippet,
                                    remediation="Use parameterized queries with bind placeholders (e.g. `cursor.execute('SELECT * FROM users WHERE id = :id', {'id': user_id})`).",
                                    confidence=0.97,
                                )
                            )

        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        lineno = getattr(node, "lineno", 1)
        end_lineno = getattr(node, "end_lineno", lineno)
        snippet = self._get_snippet(lineno, end_lineno)
        if any(k in snippet.upper() for k in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "FROM ", "WHERE ")):
            self.vulnerabilities.append(
                SecurityVulnerability(
                    rule_id="SEC-INJ-001",
                    cwe_id="CWE-89",
                    owasp_category=OWASPCategory.A03_INJECTION,
                    title="SQL Injection via string interpolation in database query",
                    description="Constructing SQL queries via string formatting or f-strings allows arbitrary SQL injection attacks.",
                    severity=VulnerabilitySeverity.CRITICAL,
                    file_path=self.file_path,
                    line_number=lineno,
                    end_line_number=end_lineno,
                    code_snippet=snippet,
                    remediation="Use parameterized queries with bind placeholders (e.g. `cursor.execute('SELECT * FROM users WHERE id = :id', {'id': user_id})`).",
                    confidence=0.97,
                )
            )
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        if isinstance(node.op, ast.Mod):
            lineno = getattr(node, "lineno", 1)
            end_lineno = getattr(node, "end_lineno", lineno)
            snippet = self._get_snippet(lineno, end_lineno)
            if any(k in snippet.upper() for k in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "FROM ", "WHERE ")):
                self.vulnerabilities.append(
                    SecurityVulnerability(
                        rule_id="SEC-INJ-001",
                        cwe_id="CWE-89",
                        owasp_category=OWASPCategory.A03_INJECTION,
                        title="SQL Injection via `%` format operator in database query",
                        description="Constructing SQL queries via `%` operator interpolation allows arbitrary SQL injection.",
                        severity=VulnerabilitySeverity.CRITICAL,
                        file_path=self.file_path,
                        line_number=lineno,
                        end_line_number=end_lineno,
                        code_snippet=snippet,
                        remediation="Use parameterized queries with bind placeholders instead of string formatting.",
                        confidence=0.97,
                    )
                )
        self.generic_visit(node)


class SecurityAgentService:
    """Specialized agent service for SAST security analysis, vulnerability scanning, and remediation."""

    def __init__(self):
        self.settings = get_settings()

    def analyze_source_code(
        self, source_code: str, file_path: str = "source.py"
    ) -> List[SecurityVulnerability]:
        """Run AST and regex SAST security rules on source code."""
        vulns: List[SecurityVulnerability] = []
        lines = source_code.splitlines(keepends=True)

        # 1. Python AST security visitor
        if file_path.endswith((".py", ".pyw")):
            try:
                tree = ast.parse(source_code)
                checker = PythonSecurityASTChecker(file_path=file_path, lines=lines)
                checker.visit(tree)
                vulns.extend(checker.vulnerabilities)
            except SyntaxError:
                pass

        # 2. Hardcoded secrets scan (integration with secrets_sanitizer)
        raw_lines = source_code.splitlines()
        for idx, line in enumerate(raw_lines, 1):
            for secret_type, pattern in secrets_sanitizer_service.KNOWN_SECRET_PATTERNS.items():
                if secret_type == "generic_api_assignment":
                    continue
                match = pattern.search(line)
                if match:
                    masked = match.group(0)[:4] + "..." + match.group(0)[-4:] if len(match.group(0)) > 8 else "***"
                    vulns.append(
                        SecurityVulnerability(
                            rule_id="SEC-AUTH-001",
                            cwe_id="CWE-798",
                            owasp_category=OWASPCategory.A07_IDENTIFICATION_FAILURES,
                            title=f"Hardcoded sensitive credential ({secret_type})",
                            description=f"Detected plaintext credential `{masked}` committed in source code.",
                            severity=VulnerabilitySeverity.HIGH,
                            file_path=file_path,
                            line_number=idx,
                            code_snippet=line.strip(),
                            remediation="Extract credentials to environment variables or an enterprise secrets manager (Vault/AWS Secrets Manager).",
                            confidence=0.98,
                        )
                    )

            # 3. Cross-Site Scripting (XSS / dangerouslySetInnerHTML / innerHTML)
            if "dangerouslySetInnerHTML" in line or (re.search(r"\.innerHTML\s*=", line) and "DOMPurify" not in line):
                vulns.append(
                    SecurityVulnerability(
                        rule_id="SEC-XSS-001",
                        cwe_id="CWE-79",
                        owasp_category=OWASPCategory.A03_INJECTION,
                        title="Potential Cross-Site Scripting (XSS) via raw HTML injection",
                        description="Injecting unescaped HTML into DOM elements enables client-side script execution and session hijacking.",
                        severity=VulnerabilitySeverity.HIGH,
                        file_path=file_path,
                        line_number=idx,
                        code_snippet=line.strip(),
                        remediation="Sanitize HTML using DOMPurify before rendering, or prefer safe text elements.",
                        confidence=0.91,
                    )
                )

        # De-duplicate findings by (rule_id, file_path, line_number)
        seen = set()
        deduped: List[SecurityVulnerability] = []
        for v in vulns:
            key = (v.rule_id, v.file_path, v.line_number)
            if key not in seen:
                seen.add(key)
                deduped.append(v)

        return deduped

    def format_summary(
        self, vulns: List[SecurityVulnerability], repo_id: str
    ) -> str:
        """Render a formatted markdown security audit report."""
        if not vulns:
            return (
                f"### DevMind Security Audit Report: `{repo_id}`\n\n"
                " **Zero high-risk security vulnerabilities detected.**\n"
                "All SAST injection, cryptographic, secret, and authentication checks passed."
            )

        crits = sum(1 for v in vulns if v.severity == VulnerabilitySeverity.CRITICAL)
        highs = sum(1 for v in vulns if v.severity == VulnerabilitySeverity.HIGH)
        meds = sum(1 for v in vulns if v.severity == VulnerabilitySeverity.MEDIUM)
        lows = sum(1 for v in vulns if v.severity == VulnerabilitySeverity.LOW)

        lines = [
            f"### DevMind Security Audit Report: `{repo_id}`",
            f"**Total Findings:** {len(vulns)} (Critical: {crits}, High: {highs}, Medium: {meds}, Low: {lows})\n",
            "| Rule | CWE | OWASP | Severity | Location | Title |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for v in vulns:
            loc = f"`{v.file_path}:{v.line_number}`"
            sev_badge = f"**{v.severity.value.upper()}**"
            lines.append(
                f"| `{v.rule_id}` | `{v.cwe_id}` | {v.owasp_category.value.split(':')[0]} | {sev_badge} | {loc} | {v.title} |"
            )

        lines.append("\n#### Detailed Security Findings & Fix Recommendations:\n")
        for i, v in enumerate(vulns, 1):
            lines.append(
                f"**{i}. [{v.rule_id} / {v.cwe_id}] {v.title}** ({v.severity.value.upper()})\n"
                f"- **OWASP Category:** {v.owasp_category.value}\n"
                f"- **Location:** `{v.file_path}:{v.line_number}`\n"
                f"- **Vulnerability Impact:** {v.description}\n"
                f"- **Vulnerable Excerpt:**\n```\n{v.code_snippet}\n```\n"
                f"- **Remediation Patch:** {v.remediation}\n"
            )

        return "\n".join(lines)

    async def audit_security(
        self,
        request: SecurityAuditRequest,
        force_offline: bool = False,
    ) -> SecurityAuditResponse:
        """Perform comprehensive SAST security audit against code snippet or repository index."""
        vulns: List[SecurityVulnerability] = []

        # 1. Direct snippet audit
        if request.code_snippet:
            target_path = request.target_path or "snippet.py"
            vulns.extend(self.analyze_source_code(request.code_snippet, target_path))

        # 2. Repository retrieval audit
        if request.repo_id and not request.code_snippet:
            search_query = request.query or "sql query execute eval exec secret password crypto md5"
            query_obj = HybridSearchQuery(
                repo_id=request.repo_id,
                query=search_query,
                top_k=8,
                alpha=0.3,
                file_path_filter=request.target_path,
            )
            search_resp = await hybrid_retriever_service.search(params=query_obj)
            for chunk in search_resp.chunks:
                chunk_vulns = self.analyze_source_code(chunk.content, chunk.file_path)
                for cv in chunk_vulns:
                    cv.line_number = chunk.start_line + max(0, cv.line_number - 1)
                    if cv.end_line_number:
                        cv.end_line_number = chunk.start_line + max(0, cv.end_line_number - 1)
                vulns.extend(chunk_vulns)

        # Apply severity filter if requested
        if request.severity_filter:
            allowed = set(request.severity_filter)
            vulns = [v for v in vulns if v.severity in allowed]

        # De-duplicate
        seen = set()
        deduped: List[SecurityVulnerability] = []
        for v in vulns:
            key = (v.rule_id, v.file_path, v.line_number)
            if key not in seen:
                seen.add(key)
                deduped.append(v)

        vulns = deduped

        # Check for online LLM enhancement
        is_mock = (
            force_offline
            or not self.settings.OPENAI_API_KEY
            or self.settings.OPENAI_API_KEY.startswith("sk-placeholder")
        )

        if not is_mock and (request.code_snippet or request.query):
            headers = {
                "Authorization": f"Bearer {self.settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            code_ctx = request.code_snippet or "Context extracted from repository."
            payload = {
                "model": self.settings.OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": SECURITY_AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Repository: {request.repo_id}\nQuery: {request.query}\nCode:\n{code_ctx}"},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(OPENAI_CHAT_URL, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    parsed = json.loads(data["choices"][0]["message"]["content"])
                    llm_vulns_raw = parsed.get("vulnerabilities", [])
                    for lv in llm_vulns_raw:
                        try:
                            v_sev = VulnerabilitySeverity(lv.get("severity", "medium").lower())
                        except ValueError:
                            v_sev = VulnerabilitySeverity.MEDIUM
                        try:
                            v_owasp = OWASPCategory(lv.get("owasp_category", OWASPCategory.A03_INJECTION.value))
                        except ValueError:
                            v_owasp = OWASPCategory.A03_INJECTION

                        vulns.append(
                            SecurityVulnerability(
                                rule_id=lv.get("rule_id", "SEC-LLM-001"),
                                cwe_id=lv.get("cwe_id", "CWE-699"),
                                owasp_category=v_owasp,
                                title=lv.get("title", "Identified Security Flaw"),
                                description=lv.get("description", "Vulnerability detected by LLM analysis"),
                                severity=v_sev,
                                file_path=lv.get("file_path", request.target_path or "source.py"),
                                line_number=int(lv.get("line_number", 1)),
                                code_snippet=lv.get("code_snippet", ""),
                                remediation=lv.get("remediation", "Apply security patch"),
                                confidence=float(lv.get("confidence", 0.9)),
                            )
                        )
                    return SecurityAuditResponse(
                        repo_id=request.repo_id,
                        total_vulnerabilities=len(vulns),
                        critical_count=sum(1 for v in vulns if v.severity == VulnerabilitySeverity.CRITICAL),
                        high_count=sum(1 for v in vulns if v.severity == VulnerabilitySeverity.HIGH),
                        medium_count=sum(1 for v in vulns if v.severity == VulnerabilitySeverity.MEDIUM),
                        low_count=sum(1 for v in vulns if v.severity == VulnerabilitySeverity.LOW),
                        vulnerabilities=vulns,
                        summary=parsed.get("summary", self.format_summary(vulns, request.repo_id)),
                        model_used=self.settings.OPENAI_MODEL,
                    )
            except Exception as e:
                logger.warning(f"LLM Security Audit failed: {e}; returning SAST static findings.")

        summary_text = self.format_summary(vulns, request.repo_id)
        return SecurityAuditResponse(
            repo_id=request.repo_id,
            total_vulnerabilities=len(vulns),
            critical_count=sum(1 for v in vulns if v.severity == VulnerabilitySeverity.CRITICAL),
            high_count=sum(1 for v in vulns if v.severity == VulnerabilitySeverity.HIGH),
            medium_count=sum(1 for v in vulns if v.severity == VulnerabilitySeverity.MEDIUM),
            low_count=sum(1 for v in vulns if v.severity == VulnerabilitySeverity.LOW),
            vulnerabilities=vulns,
            summary=summary_text,
            model_used="sast-pattern-analyzer",
        )


security_agent_service = SecurityAgentService()
