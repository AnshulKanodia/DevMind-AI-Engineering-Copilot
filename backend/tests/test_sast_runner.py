import json
import sys
from pathlib import Path
import pytest

from app.schemas.sast import SASTRunnerRequest, SASTTool
from app.services.sast_runner import sast_runner_service


def test_normalize_bandit_output():
    raw_bandit = json.dumps(
        {
            "results": [
                {
                    "test_id": "B301",
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                    "issue_text": "Pickle deserialization is unsafe.",
                    "filename": "app/session.py",
                    "line_number": 24,
                    "code": "pickle.loads(data)",
                    "issue_cwe": {"id": 502},
                }
            ]
        }
    )
    alerts = sast_runner_service.normalize_bandit_output(raw_bandit)
    assert len(alerts) == 1
    assert alerts[0].tool == SASTTool.BANDIT
    assert alerts[0].rule_id == "B301"
    assert alerts[0].severity == "HIGH"
    assert alerts[0].cwe_id == "CWE-502"
    assert alerts[0].line_number == 24


def test_normalize_semgrep_output():
    raw_semgrep = json.dumps(
        {
            "results": [
                {
                    "check_id": "python.lang.security.audit.sqli",
                    "path": "app/db.py",
                    "start": {"line": 12},
                    "extra": {
                        "severity": "ERROR",
                        "message": "Formatted SQL query detected",
                        "lines": "cursor.execute(f'SELECT * FROM t WHERE id={x}')",
                        "metadata": {"cwe": ["CWE-89: SQL Injection"], "confidence": "HIGH"},
                    },
                }
            ]
        }
    )
    alerts = sast_runner_service.normalize_semgrep_output(raw_semgrep)
    assert len(alerts) == 1
    assert alerts[0].tool == SASTTool.SEMGREP
    assert alerts[0].severity == "HIGH"
    assert alerts[0].cwe_id == "CWE-89"
    assert alerts[0].line_number == 12


def test_normalize_eslint_output():
    raw_eslint = json.dumps(
        [
            {
                "filePath": "src/App.tsx",
                "messages": [
                    {
                        "ruleId": "no-eval",
                        "severity": 2,
                        "message": "eval can be harmful.",
                        "line": 8,
                        "source": "eval(userCode);",
                    }
                ],
            }
        ]
    )
    alerts = sast_runner_service.normalize_eslint_output(raw_eslint)
    assert len(alerts) == 1
    assert alerts[0].tool == SASTTool.ESLINT
    assert alerts[0].rule_id == "no-eval"
    assert alerts[0].severity == "HIGH"
    assert alerts[0].line_number == 8


@pytest.mark.asyncio
async def test_run_scan_python_bandit_and_semgrep():
    py_code = """
import pickle
import subprocess

def handle_payload(raw_bytes, user_id):
    obj = pickle.loads(raw_bytes)
    subprocess.Popen("ls -la", shell=True)
    query = f"SELECT * FROM accounts WHERE id = {user_id}"
    return eval("1 + 1")
"""
    req = SASTRunnerRequest(
        repo_id="test-sast-py",
        target_path="app/worker.py",
        code_snippet=py_code,
        tools=[SASTTool.BANDIT, SASTTool.SEMGREP],
    )
    resp = await sast_runner_service.run_scan(req)

    assert resp.total_alerts >= 4
    rule_ids = {a.rule_id for a in resp.alerts}
    assert "B301" in rule_ids
    assert "B602" in rule_ids
    assert "B307" in rule_ids
    assert "python.lang.security.audit.formatted-sql-query" in rule_ids


@pytest.mark.asyncio
async def test_run_scan_typescript_eslint():
    ts_code = """
export function UnsafeWidget({ rawHtml, code }: { rawHtml: string; code: string }) {
    eval(code);
    return <div dangerouslySetInnerHTML={{ __html: rawHtml }} />;
}
"""
    req = SASTRunnerRequest(
        repo_id="test-sast-ts",
        target_path="src/components/UnsafeWidget.tsx",
        code_snippet=ts_code,
        tools=[SASTTool.ESLINT],
    )
    resp = await sast_runner_service.run_scan(req)

    assert resp.total_alerts == 2
    rule_ids = {a.rule_id for a in resp.alerts}
    assert "no-eval" in rule_ids
    assert "react/no-danger" in rule_ids


@pytest.mark.asyncio
async def test_isolated_subprocess_timeout_enforcement(tmp_path: Path):
    _, _, timed_out = await sast_runner_service._run_isolated_subprocess(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        timeout_seconds=1,
    )
    assert timed_out is True
