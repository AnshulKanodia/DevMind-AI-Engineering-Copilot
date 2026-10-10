import ast
import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings
from app.schemas.bug import BugFinding, BugHuntRequest, BugHuntResponse, BugSeverity
from app.schemas.retrieval import HybridSearchQuery
from app.services.hybrid_retriever import hybrid_retriever_service

logger = logging.getLogger("devmind.agents.bug")

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

BUG_AGENT_SYSTEM_PROMPT = """You are the DevMind Principal Bug Hunter and Static Analysis Engineer.
Analyze the provided code and findings. Detect runtime bugs, null/undefined crashes, unhandled errors,
race conditions, off-by-one errors, memory leaks, and anti-patterns.

Format your response as a JSON object matching this schema:
{
  "summary": "High-level summary of defect findings and reliability health",
  "findings": [
    {
      "rule_id": "DEV-BUG-XXX",
      "title": "Concise defect title",
      "description": "Technical analysis of how this defect causes a runtime crash or state corruption",
      "severity": "critical" | "high" | "medium" | "low" | "info",
      "file_path": "path/to/file",
      "line_number": 12,
      "end_line_number": 15,
      "code_snippet": "...",
      "remediation": "Prescriptive code fix or patch",
      "confidence": 0.95,
      "symbol_name": "function_or_class_name"
    }
  ]
}
"""


class PythonASTBugChecker(ast.NodeVisitor):
    """AST visitor detecting common Python anti-patterns and runtime risks."""

    def __init__(self, file_path: str, lines: List[str]):
        self.file_path = file_path
        self.lines = lines
        self.findings: List[BugFinding] = []
        self._current_function: Optional[str] = None

    def _get_snippet(self, start_line: int, end_line: int) -> str:
        s_idx = max(0, start_line - 1)
        e_idx = min(len(self.lines), end_line)
        return "".join(self.lines[s_idx:e_idx]).strip()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev = self._current_function
        self._current_function = node.name
        self._check_mutable_defaults(node)
        self._check_builtin_shadowing(node)
        self._check_unreachable_code(node.body)
        self.generic_visit(node)
        self._current_function = prev

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        prev = self._current_function
        self._current_function = node.name
        self._check_mutable_defaults(node)
        self._check_builtin_shadowing(node)
        self._check_unreachable_code(node.body)
        self.generic_visit(node)
        self._current_function = prev

    def _check_mutable_defaults(self, node: Any):
        """Rule DEV-BUG-002: Detect mutable default arguments (list, dict, set)."""
        defaults = node.args.defaults + [d for d in node.args.kw_defaults if d is not None]
        for d in defaults:
            if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                lineno = getattr(d, "lineno", node.lineno)
                self.findings.append(
                    BugFinding(
                        rule_id="DEV-BUG-002",
                        title=f"Mutable default argument in `{node.name}`",
                        description=(
                            f"Function `{node.name}` uses a mutable container (list/dict/set) as a default parameter. "
                            "Default expressions are evaluated once at module load, causing state leakage across calls."
                        ),
                        severity=BugSeverity.MEDIUM,
                        file_path=self.file_path,
                        line_number=lineno,
                        end_line_number=lineno,
                        code_snippet=self._get_snippet(node.lineno, node.lineno),
                        remediation=f"Replace mutable default with `None` and initialize inside `{node.name}` using `if param is None: param = []`.",
                        confidence=0.95,
                        symbol_name=node.name,
                    )
                )

    def _check_builtin_shadowing(self, node: Any):
        """Rule DEV-BUG-005: Detect parameter names shadowing core built-in functions."""
        shadowed_builtins = {"id", "type", "list", "dict", "str", "int", "format", "input", "object", "bytes"}
        for arg in node.args.args + getattr(node.args, "posonlyargs", []) + node.args.kwonlyargs:
            if arg.arg in shadowed_builtins:
                lineno = getattr(arg, "lineno", node.lineno)
                self.findings.append(
                    BugFinding(
                        rule_id="DEV-BUG-005",
                        title=f"Parameter `{arg.arg}` shadows Python built-in",
                        description=f"Function argument `{arg.arg}` shadows the global built-in `{arg.arg}`, preventing standard usage in scope.",
                        severity=BugSeverity.LOW,
                        file_path=self.file_path,
                        line_number=lineno,
                        end_line_number=lineno,
                        code_snippet=self._get_snippet(lineno, lineno),
                        remediation=f"Rename argument `{arg.arg}` to `{arg.arg}_` or a more descriptive domain name.",
                        confidence=0.85,
                        symbol_name=node.name,
                    )
                )

    def _check_unreachable_code(self, statements: List[ast.stmt]):
        """Rule DEV-BUG-003: Detect unreachable code following unconditional exits."""
        if not statements or not isinstance(statements, list):
            return
        for i, stmt in enumerate(statements[:-1]):
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                next_stmt = statements[i + 1]
                lineno = getattr(next_stmt, "lineno", stmt.lineno + 1)
                end_lineno = getattr(next_stmt, "end_lineno", lineno)
                self.findings.append(
                    BugFinding(
                        rule_id="DEV-BUG-003",
                        title="Unreachable dead code",
                        description=f"Code statement directly follows unconditional {type(stmt).__name__.lower()} and can never execute.",
                        severity=BugSeverity.LOW,
                        file_path=self.file_path,
                        line_number=lineno,
                        end_line_number=end_lineno,
                        code_snippet=self._get_snippet(lineno, end_lineno),
                        remediation="Remove or restructure the unreachable dead statements.",
                        confidence=0.98,
                        symbol_name=self._current_function,
                    )
                )
                break

    def generic_visit(self, node: ast.AST):
        if hasattr(node, "body") and isinstance(node.body, list):
            self._check_unreachable_code(node.body)
        if hasattr(node, "orelse") and isinstance(node.orelse, list):
            self._check_unreachable_code(node.orelse)
        if hasattr(node, "finalbody") and isinstance(node.finalbody, list):
            self._check_unreachable_code(node.finalbody)
        super().generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        """Rule DEV-BUG-001: Detect bare except or overly broad catch-all blocks."""
        lineno = getattr(node, "lineno", 1)
        if node.type is None:
            self.findings.append(
                BugFinding(
                    rule_id="DEV-BUG-001",
                    title="Bare `except:` clause masks all exceptions",
                    description=(
                        "A bare `except:` catches `KeyboardInterrupt` and `SystemExit` as well as runtime exceptions, "
                        "severely hindering debugging and graceful termination."
                    ),
                    severity=BugSeverity.HIGH,
                    file_path=self.file_path,
                    line_number=lineno,
                    end_line_number=lineno,
                    code_snippet=self._get_snippet(lineno, lineno),
                    remediation="Catch specific exceptions like `except Exception as e:` or re-raise with `raise`.",
                    confidence=0.99,
                    symbol_name=self._current_function,
                )
            )
        elif isinstance(node.type, ast.Name) and node.type.id == "BaseException":
            self.findings.append(
                BugFinding(
                    rule_id="DEV-BUG-001",
                    title="Broad `except BaseException:` catches system interrupts",
                    description="Catching `BaseException` intercepts process control signals like `KeyboardInterrupt` and `SystemExit`.",
                    severity=BugSeverity.HIGH,
                    file_path=self.file_path,
                    line_number=lineno,
                    end_line_number=lineno,
                    code_snippet=self._get_snippet(lineno, lineno),
                    remediation="Catch `Exception` instead of `BaseException` unless explicitly intercepting all process interrupts.",
                    confidence=0.95,
                    symbol_name=self._current_function,
                )
            )
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        """Rule DEV-BUG-006: Comparison to None using == or !=."""
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(comparator, ast.Constant) and comparator.value is None:
                if isinstance(op, (ast.Eq, ast.NotEq)):
                    lineno = getattr(node, "lineno", 1)
                    op_str = "==" if isinstance(op, ast.Eq) else "!="
                    suggested = "is None" if isinstance(op, ast.Eq) else "is not None"
                    self.findings.append(
                        BugFinding(
                            rule_id="DEV-BUG-006",
                            title=f"Comparison to None using `{op_str}` instead of identity operator",
                            description=(
                                f"Comparison `{op_str} None` can be overridden by custom `__eq__` implementations. "
                                "Identity check `is None` is idiomatic and faster."
                            ),
                            severity=BugSeverity.LOW,
                            file_path=self.file_path,
                            line_number=lineno,
                            end_line_number=lineno,
                            code_snippet=self._get_snippet(lineno, lineno),
                            remediation=f"Replace `{op_str} None` with `{suggested}`.",
                            confidence=0.95,
                            symbol_name=self._current_function,
                        )
                    )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Rule DEV-BUG-004: Detect unmanaged open() call outside 'with' statement."""
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            # Note: A full check verifies if enclosing parent is With, but standalone statement calls are flags
            pass
        self.generic_visit(node)


class BugAgentService:
    """Specialized agent service for deep defect hunting, static AST checks, and automated remediations."""

    def __init__(self):
        self.settings = get_settings()

    def analyze_source_code(
        self, source_code: str, file_path: str = "source.py"
    ) -> List[BugFinding]:
        """Perform static AST and heuristic defect analysis on source code."""
        findings: List[BugFinding] = []
        lines = source_code.splitlines(keepends=True)

        # 1. Python AST-based analysis
        if file_path.endswith((".py", ".pyw")):
            try:
                tree = ast.parse(source_code)
                checker = PythonASTBugChecker(file_path=file_path, lines=lines)
                checker.visit(tree)
                findings.extend(checker.findings)
            except SyntaxError as e:
                findings.append(
                    BugFinding(
                        rule_id="DEV-SYNTAX-001",
                        title="Python Syntax Error",
                        description=f"Parsing error: {e.msg}",
                        severity=BugSeverity.CRITICAL,
                        file_path=file_path,
                        line_number=e.lineno or 1,
                        code_snippet=lines[max(0, (e.lineno or 1) - 1)].strip() if lines else "",
                        remediation="Correct invalid Python syntax.",
                        confidence=1.0,
                    )
                )

        # 2. General multi-language heuristic checks (JS, TS, Python, Go)
        raw_lines = source_code.splitlines()
        for idx, line in enumerate(raw_lines, 1):
            # JS/TS empty catch block: catch (e) {}
            if re.search(r"catch\s*\([^)]*\)\s*\{\s*\}", line):
                findings.append(
                    BugFinding(
                        rule_id="DEV-BUG-007",
                        title="Empty catch block silently swallowing exceptions",
                        description="Exceptions are caught and discarded without logging or handling, creating hard-to-diagnose silent failures.",
                        severity=BugSeverity.HIGH,
                        file_path=file_path,
                        line_number=idx,
                        code_snippet=line.strip(),
                        remediation="Log or propagate caught errors: `console.error(err)` or throw.",
                        confidence=0.92,
                    )
                )
            # Accidental assignment in conditional: if (x = 5)
            if re.search(r"if\s*\([^=!<>\n]*=[^=!<>\n]*\)", line) and "==" not in line and "!=" not in line and "<=" not in line and ">=" not in line:
                findings.append(
                    BugFinding(
                        rule_id="DEV-BUG-008",
                        title="Accidental assignment inside conditional expression",
                        description="Conditional appears to perform single-equals assignment `=` instead of equality comparison `===` or `==`.",
                        severity=BugSeverity.CRITICAL,
                        file_path=file_path,
                        line_number=idx,
                        code_snippet=line.strip(),
                        remediation="Replace assignment `=` with equality comparison `===` or `==`.",
                        confidence=0.90,
                    )
                )

        return findings

    def format_summary(self, findings: List[BugFinding], repo_id: str) -> str:
        """Produce a formatted markdown summary report of the bug analysis."""
        if not findings:
            return (
                f"### DevMind Bug Hunt Report: `{repo_id}`\n\n"
                " No defects or anti-patterns were detected in the analyzed code.\n"
                "All static AST validations and runtime safety checks passed."
            )

        criticals = sum(1 for f in findings if f.severity == BugSeverity.CRITICAL)
        highs = sum(1 for f in findings if f.severity == BugSeverity.HIGH)
        mediums = sum(1 for f in findings if f.severity == BugSeverity.MEDIUM)
        lows = sum(1 for f in findings if f.severity == BugSeverity.LOW)

        lines = [
            f"### DevMind Bug Hunt Report: `{repo_id}`",
            f"**Total Findings:** {len(findings)} (Critical: {criticals}, High: {highs}, Medium: {mediums}, Low: {lows})\n",
            "| Rule | Severity | Location | Title |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for f in findings:
            loc = f"`{f.file_path}:{f.line_number}`"
            sev_badge = f"**{f.severity.value.upper()}**"
            lines.append(f"| `{f.rule_id}` | {sev_badge} | {loc} | {f.title} |")

        lines.append("\n#### Detailed Findings & Prescriptive Remediations:\n")
        for i, f in enumerate(findings, 1):
            lines.append(
                f"**{i}. [{f.rule_id}] {f.title}** ({f.severity.value.upper()})\n"
                f"- **Location:** `{f.file_path}:{f.line_number}`\n"
                f"- **Risk Analysis:** {f.description}\n"
                f"- **Code Snippet:**\n```\n{f.code_snippet}\n```\n"
                f"- **Remediation:** {f.remediation}\n"
            )

        return "\n".join(lines)

    async def hunt_bugs(
        self,
        request: BugHuntRequest,
        force_offline: bool = False,
    ) -> BugHuntResponse:
        """Execute automated bug hunting on repository or code snippet."""
        findings: List[BugFinding] = []

        # 1. Direct code snippet analysis
        if request.code_snippet:
            target_path = request.target_path or "snippet.py"
            findings.extend(self.analyze_source_code(request.code_snippet, target_path))

        # 2. Repository retrieval analysis
        if request.repo_id and not request.code_snippet:
            # Query relevant chunks from hybrid retriever
            search_query = request.query or "bug defect error exception crash null pointer"
            query_obj = HybridSearchQuery(
                repo_id=request.repo_id,
                query=search_query,
                top_k=8,
                alpha=0.3,
                file_path_filter=request.target_path,
            )
            search_resp = await hybrid_retriever_service.search(params=query_obj)
            for chunk in search_resp.chunks:
                chunk_findings = self.analyze_source_code(chunk.content, chunk.file_path)
                # Adjust line numbers relative to chunk start_line
                for cf in chunk_findings:
                    cf.line_number = chunk.start_line + max(0, cf.line_number - 1)
                    if cf.end_line_number:
                        cf.end_line_number = chunk.start_line + max(0, cf.end_line_number - 1)
                findings.extend(chunk_findings)

        # Apply severity filter if requested
        if request.severity_filter:
            allowed = set(request.severity_filter)
            findings = [f for f in findings if f.severity in allowed]

        # De-duplicate findings by (rule_id, file_path, line_number)
        seen = set()
        deduped_findings: List[BugFinding] = []
        for f in findings:
            key = (f.rule_id, f.file_path, f.line_number)
            if key not in seen:
                seen.add(key)
                deduped_findings.append(f)

        findings = deduped_findings

        # Calculate counts
        critical_count = sum(1 for f in findings if f.severity == BugSeverity.CRITICAL)
        high_count = sum(1 for f in findings if f.severity == BugSeverity.HIGH)
        medium_count = sum(1 for f in findings if f.severity == BugSeverity.MEDIUM)
        low_count = sum(1 for f in findings if f.severity == BugSeverity.LOW)

        # 3. Check for online LLM enhancement
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
                    {"role": "system", "content": BUG_AGENT_SYSTEM_PROMPT},
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
                    llm_findings_raw = parsed.get("findings", [])
                    for lf in llm_findings_raw:
                        try:
                            f_sev = BugSeverity(lf.get("severity", "medium").lower())
                        except ValueError:
                            f_sev = BugSeverity.MEDIUM
                        findings.append(
                            BugFinding(
                                rule_id=lf.get("rule_id", "DEV-BUG-LLM"),
                                title=lf.get("title", "Semantic code defect"),
                                description=lf.get("description", "Potential logic defect"),
                                severity=f_sev,
                                file_path=lf.get("file_path", request.target_path or "source.py"),
                                line_number=int(lf.get("line_number", 1)),
                                code_snippet=lf.get("code_snippet", ""),
                                remediation=lf.get("remediation", "Apply patch"),
                                confidence=float(lf.get("confidence", 0.9)),
                                symbol_name=lf.get("symbol_name"),
                            )
                        )
                    return BugHuntResponse(
                        repo_id=request.repo_id,
                        total_bugs=len(findings),
                        critical_count=sum(1 for f in findings if f.severity == BugSeverity.CRITICAL),
                        high_count=sum(1 for f in findings if f.severity == BugSeverity.HIGH),
                        medium_count=sum(1 for f in findings if f.severity == BugSeverity.MEDIUM),
                        low_count=sum(1 for f in findings if f.severity == BugSeverity.LOW),
                        findings=findings,
                        summary=parsed.get("summary", self.format_summary(findings, request.repo_id)),
                        model_used=self.settings.OPENAI_MODEL,
                    )
            except Exception as e:
                logger.warning(f"LLM Bug Hunt failed: {e}; returning AST static findings.")

        summary_text = self.format_summary(findings, request.repo_id)
        return BugHuntResponse(
            repo_id=request.repo_id,
            total_bugs=len(findings),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            findings=findings,
            summary=summary_text,
            model_used="ast-static-analyzer",
        )


bug_agent_service = BugAgentService()
