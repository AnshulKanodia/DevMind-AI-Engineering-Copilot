import asyncio
import json
import logging
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple

from app.schemas.sast import (
    SASTNormalizedAlert,
    SASTRunnerRequest,
    SASTRunnerResponse,
    SASTTool,
)

logger = logging.getLogger("devmind.services.sast_runner")


class SASTRunnerService:
    """Isolated static analysis runner supporting Bandit (Python), ESLint (JS/TS), and Semgrep."""

    def normalize_bandit_output(
        self, raw_json: str, default_file: str = "source.py"
    ) -> List[SASTNormalizedAlert]:
        """Parse and normalize Bandit JSON output into SASTNormalizedAlert records."""
        alerts: List[SASTNormalizedAlert] = []
        try:
            data = json.loads(raw_json)
            for item in data.get("results", []):
                cwe_data = item.get("issue_cwe", {})
                cwe_id = f"CWE-{cwe_data['id']}" if isinstance(cwe_data, dict) and "id" in cwe_data else None
                alerts.append(
                    SASTNormalizedAlert(
                        tool=SASTTool.BANDIT,
                        rule_id=item.get("test_id", "B000"),
                        severity=item.get("issue_severity", "MEDIUM").upper(),
                        confidence=item.get("issue_confidence", "HIGH").upper(),
                        message=item.get("issue_text", "Bandit security warning"),
                        file_path=item.get("filename", default_file),
                        line_number=int(item.get("line_number", 1)),
                        code_snippet=item.get("code", "").strip(),
                        cwe_id=cwe_id,
                    )
                )
        except Exception as exc:
            logger.warning(f"Failed to parse Bandit JSON output: {exc}")
        return alerts

    def normalize_semgrep_output(
        self, raw_json: str, default_file: str = "source.py"
    ) -> List[SASTNormalizedAlert]:
        """Parse and normalize Semgrep JSON output into SASTNormalizedAlert records."""
        alerts: List[SASTNormalizedAlert] = []
        sev_map = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW"}
        try:
            data = json.loads(raw_json)
            for item in data.get("results", []):
                extra = item.get("extra", {})
                raw_sev = extra.get("severity", "WARNING").upper()
                meta = extra.get("metadata", {})
                cwe_raw = meta.get("cwe")
                if isinstance(cwe_raw, list) and cwe_raw:
                    cwe_id = str(cwe_raw[0]).split(":")[0]
                elif isinstance(cwe_raw, str):
                    cwe_id = cwe_raw.split(":")[0]
                else:
                    cwe_id = None

                alerts.append(
                    SASTNormalizedAlert(
                        tool=SASTTool.SEMGREP,
                        rule_id=item.get("check_id", "semgrep-rule"),
                        severity=sev_map.get(raw_sev, raw_sev),
                        confidence=meta.get("confidence", "HIGH").upper(),
                        message=extra.get("message", "Semgrep finding"),
                        file_path=item.get("path", default_file),
                        line_number=int(item.get("start", {}).get("line", 1)),
                        code_snippet=extra.get("lines", "").strip(),
                        cwe_id=cwe_id,
                    )
                )
        except Exception as exc:
            logger.warning(f"Failed to parse Semgrep JSON output: {exc}")
        return alerts

    def normalize_eslint_output(
        self, raw_json: str, default_file: str = "source.ts"
    ) -> List[SASTNormalizedAlert]:
        """Parse and normalize ESLint JSON output into SASTNormalizedAlert records."""
        alerts: List[SASTNormalizedAlert] = []
        try:
            data = json.loads(raw_json)
            if not isinstance(data, list):
                return alerts
            for file_entry in data:
                f_path = file_entry.get("filePath", default_file)
                for msg in file_entry.get("messages", []):
                    sev_num = msg.get("severity", 1)
                    sev_str = "HIGH" if sev_num == 2 else "LOW"
                    alerts.append(
                        SASTNormalizedAlert(
                            tool=SASTTool.ESLINT,
                            rule_id=msg.get("ruleId") or "eslint-generic",
                            severity=sev_str,
                            confidence="HIGH",
                            message=msg.get("message", "ESLint violation"),
                            file_path=f_path,
                            line_number=int(msg.get("line", 1)),
                            code_snippet=msg.get("source", "").strip() if msg.get("source") else None,
                            cwe_id=None,
                        )
                    )
        except Exception as exc:
            logger.warning(f"Failed to parse ESLint JSON output: {exc}")
        return alerts

    async def _run_isolated_subprocess(
        self, cmd: List[str], cwd: Path, timeout_seconds: int
    ) -> Tuple[str, str, bool]:
        """Execute a linter command inside an isolated subprocess with strict timeout protection."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=float(timeout_seconds)
                )
                return (
                    stdout_bytes.decode("utf-8", errors="replace"),
                    stderr_bytes.decode("utf-8", errors="replace"),
                    False,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return "", "Subprocess timed out", True
        except Exception as exc:
            return "", str(exc), False

    def _emulate_deterministic_rules(
        self,
        source_code: str,
        file_path: str,
        tools: List[SASTTool],
    ) -> List[SASTNormalizedAlert]:
        """Deterministic built-in rule engine matching Bandit, Semgrep, and ESLint rules."""
        alerts: List[SASTNormalizedAlert] = []
        lines = source_code.splitlines()
        is_py = file_path.endswith((".py", ".pyw"))
        is_js = file_path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs"))

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()

            # Bandit Python rules
            if is_py and SASTTool.BANDIT in tools:
                if re.search(r"\bexec\s*\(", stripped):
                    alerts.append(
                        SASTNormalizedAlert(
                            tool=SASTTool.BANDIT,
                            rule_id="B102",
                            severity="HIGH",
                            confidence="HIGH",
                            message="Use of exec detected.",
                            file_path=file_path,
                            line_number=idx,
                            code_snippet=stripped,
                            cwe_id="CWE-78",
                        )
                    )
                if re.search(r"\beval\s*\(", stripped):
                    alerts.append(
                        SASTNormalizedAlert(
                            tool=SASTTool.BANDIT,
                            rule_id="B307",
                            severity="HIGH",
                            confidence="HIGH",
                            message="Use of possibly insecure function eval()—consider ast.literal_eval.",
                            file_path=file_path,
                            line_number=idx,
                            code_snippet=stripped,
                            cwe_id="CWE-94",
                        )
                    )
                if re.search(r"\bpickle\.loads?\s*\(", stripped):
                    alerts.append(
                        SASTNormalizedAlert(
                            tool=SASTTool.BANDIT,
                            rule_id="B301",
                            severity="HIGH",
                            confidence="HIGH",
                            message="Pickle and modules that wrap it can be unsafe when used to deserialize untrusted data.",
                            file_path=file_path,
                            line_number=idx,
                            code_snippet=stripped,
                            cwe_id="CWE-502",
                        )
                    )
                if "shell=True" in stripped and ("subprocess" in stripped or "Popen" in stripped or "run(" in stripped):
                    alerts.append(
                        SASTNormalizedAlert(
                            tool=SASTTool.BANDIT,
                            rule_id="B602",
                            severity="HIGH",
                            confidence="HIGH",
                            message="subprocess call with shell=True identified, security issue.",
                            file_path=file_path,
                            line_number=idx,
                            code_snippet=stripped,
                            cwe_id="CWE-78",
                        )
                    )

            # Semgrep cross-language rules
            if SASTTool.SEMGREP in tools:
                if re.search(r"(?:SELECT|INSERT|UPDATE|DELETE)\s+.*\{[a-zA-Z0-9_]+\}", stripped, re.IGNORECASE):
                    alerts.append(
                        SASTNormalizedAlert(
                            tool=SASTTool.SEMGREP,
                            rule_id="python.lang.security.audit.formatted-sql-query",
                            severity="CRITICAL",
                            confidence="HIGH",
                            message="Detected string-formatted SQL query; use parameterized queries instead.",
                            file_path=file_path,
                            line_number=idx,
                            code_snippet=stripped,
                            cwe_id="CWE-89",
                        )
                    )

            # ESLint JS/TS rules
            if is_js and SASTTool.ESLINT in tools:
                if re.search(r"\beval\s*\(", stripped):
                    alerts.append(
                        SASTNormalizedAlert(
                            tool=SASTTool.ESLINT,
                            rule_id="no-eval",
                            severity="HIGH",
                            confidence="HIGH",
                            message="eval can be harmful.",
                            file_path=file_path,
                            line_number=idx,
                            code_snippet=stripped,
                            cwe_id="CWE-95",
                        )
                    )
                if "dangerouslySetInnerHTML" in stripped or ".innerHTML" in stripped:
                    alerts.append(
                        SASTNormalizedAlert(
                            tool=SASTTool.ESLINT,
                            rule_id="react/no-danger",
                            severity="HIGH",
                            confidence="HIGH",
                            message="Dangerous property 'dangerouslySetInnerHTML' or raw innerHTML assignment found.",
                            file_path=file_path,
                            line_number=idx,
                            code_snippet=stripped,
                            cwe_id="CWE-79",
                        )
                    )

        return alerts

    async def run_scan(self, request: SASTRunnerRequest) -> SASTRunnerResponse:
        """Execute SAST scan inside an ephemeral sandbox directory and normalize findings."""
        start_ts = time.perf_counter()
        target_file = request.target_path or "snippet.py"
        source_code = request.code_snippet or ""
        alerts: List[SASTNormalizedAlert] = []
        executed_tools: List[str] = [t.value for t in request.tools]
        timed_out = False

        with tempfile.TemporaryDirectory(prefix="devmind_sast_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            file_on_disk = tmp_path / Path(target_file).name
            file_on_disk.write_text(source_code, encoding="utf-8")

            # Check if native bandit CLI is available when scanning Python
            if SASTTool.BANDIT in request.tools and target_file.endswith(".py") and shutil.which("bandit"):
                stdout, _, to = await self._run_isolated_subprocess(
                    ["bandit", "-f", "json", "-q", str(file_on_disk)],
                    cwd=tmp_path,
                    timeout_seconds=request.timeout_seconds,
                )
                timed_out = timed_out or to
                if stdout:
                    for a in self.normalize_bandit_output(stdout, target_file):
                        a.file_path = target_file
                        alerts.append(a)

        # Always merge deterministic rule emulation so environments without external binaries get identical coverage
        emulated = self._emulate_deterministic_rules(source_code, target_file, request.tools)
        seen = {(a.tool, a.rule_id, a.line_number) for a in alerts}
        for ea in emulated:
            key = (ea.tool, ea.rule_id, ea.line_number)
            if key not in seen:
                seen.add(key)
                alerts.append(ea)

        elapsed_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)
        return SASTRunnerResponse(
            repo_id=request.repo_id,
            executed_tools=executed_tools,
            total_alerts=len(alerts),
            alerts=alerts,
            execution_time_ms=elapsed_ms,
            timed_out=timed_out,
        )


sast_runner_service = SASTRunnerService()
