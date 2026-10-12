import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.bug import BugHuntRequest
from app.schemas.retrieval import HybridSearchResponse, RetrievedChunk
from app.schemas.sast import SASTRunnerRequest, SASTTool
from app.schemas.security import (
    OWASPCategory,
    SecurityAuditRequest,
)
from app.services.bug_agent import bug_agent_service
from app.services.sast_runner import sast_runner_service
from app.services.security_agent import security_agent_service

client = TestClient(app)


# ============================================================================
# Synthetic Vulnerable & Hardened Codebase Fixtures
# ============================================================================

SYNTHETIC_VULNERABLE_PYTHON_APP = """import hashlib
import os
import pickle
import subprocess
import yaml

# Hardcoded credential (CWE-798)
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def authenticate_user(cursor, username: str, password: str, audit_trail=[]):
    # Bug: Mutable default argument (DEV-BUG-002)
    # Security: Weak MD5 password hashing (CWE-328)
    password_hash = hashlib.md5(password.encode("utf-8")).hexdigest()

    # Security: SQL Injection via f-string (CWE-89)
    query = f"SELECT id, role FROM users WHERE username = '{username}' AND password_hash = '{password_hash}'"
    cursor.execute(query)
    return cursor.fetchone()


def run_diagnostic_command(host: str, raw_expr: str):
    # Security: OS Command Injection via os.system and subprocess shell=True (CWE-78)
    os.system(f"ping -c 1 {host}")
    subprocess.run(f"traceroute {host}", shell=True)

    # Security: Arbitrary code execution via eval and exec (CWE-94)
    result = eval(raw_expr)
    exec("last_status = 1")
    return result


def load_session_payload(serialized_blob: bytes, yaml_config: str):
    # Security: Insecure Deserialization via pickle and yaml.load (CWE-502)
    session_obj = pickle.loads(serialized_blob)
    cfg = yaml.load(yaml_config)
    return session_obj, cfg


def read_customer_export(file_name: str, id: str = "export-1"):
    # Bug: Built-in shadowing via parameter `id` (DEV-BUG-005)
    # Security: Path Traversal via unvalidated path join (CWE-22)
    f = open(f"/var/data/exports/{file_name}", "r")
    try:
        content = f.read()
        if content == None:  # Bug: Comparison to None using == (DEV-BUG-006)
            return ""
        return content
        print("Cleanup completed")  # Bug: Unreachable dead code (DEV-BUG-003)
    except:  # Bug: Bare except block (DEV-BUG-001)
        return None
"""

SYNTHETIC_VULNERABLE_TS_COMPONENT = """import React from "react";

export function UserCommentPreview({ rawHtml, dynamicScript, userInput }: any) {
    // Security: Cross-Site Scripting via raw innerHTML and dangerouslySetInnerHTML (CWE-79)
    const container = document.getElementById("preview-pane");
    if (container) {
        container.innerHTML = rawHtml;
    }

    // Security: Dynamic JS evaluation (CWE-95)
    const computed = eval(dynamicScript);

    // Bug: Empty catch block (DEV-BUG-007)
    try {
        JSON.parse(userInput);
    } catch (err) {}

    return <div dangerouslySetInnerHTML={{ __html: rawHtml }} />;
}
"""

SYNTHETIC_HARDENED_PYTHON_MODULE = """import hashlib
import hmac
import subprocess
from pathlib import Path
from typing import List, Optional


def verify_password_digest(password: str, salt: bytes, expected_digest: str) -> bool:
    \"\"\"Compute PBKDF2-HMAC-SHA256 digest and compare in constant time.\"\"\"
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return hmac.compare_digest(derived.hex(), expected_digest)


def fetch_user_by_id(cursor, user_id: int, tags: Optional[List[str]] = None) -> dict:
    \"\"\"Execute parameterized SQL query with safe immutable default arguments.\"\"\"
    active_tags = list(tags) if tags is not None else []
    cursor.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    return {"user": row, "tags": active_tags}


def ping_host_safely(ip_address: str) -> int:
    \"\"\"Run ping command using argument list without shell interpolation.\"\"\"
    completed = subprocess.run(
        ["ping", "-c", "1", ip_address],
        shell=False,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode


def read_config_safely(config_path: Path) -> str:
    \"\"\"Read file inside a context manager with explicit exception handling.\"\"\"
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise RuntimeError(f"Failed to read configuration: {exc}") from exc
"""


# ============================================================================
# 1. End-to-End SAST Runner Recall Tests
# ============================================================================


@pytest.mark.asyncio
async def test_sast_runner_detects_all_vulnerable_python_patterns():
    """Verify Bandit + Semgrep SAST runner detects exec, eval, pickle, subprocess shell=True, and formatted SQL."""
    req = SASTRunnerRequest(
        repo_id="synth-vuln-repo",
        code_snippet=SYNTHETIC_VULNERABLE_PYTHON_APP,
        target_path="backend/vulnerable_service.py",
        tools=[SASTTool.BANDIT, SASTTool.SEMGREP],
    )
    res = await sast_runner_service.run_scan(req)

    assert res.total_alerts >= 5
    rule_ids = {a.rule_id for a in res.alerts}
    cwe_ids = {a.cwe_id for a in res.alerts if a.cwe_id}

    # Verify Bandit rules
    assert "B102" in rule_ids  # exec()
    assert "B307" in rule_ids  # eval()
    assert "B301" in rule_ids  # pickle.loads()
    assert "B602" in rule_ids  # subprocess(..., shell=True)

    # Verify Semgrep SQLi rule
    assert "python.lang.security.audit.formatted-sql-query" in rule_ids

    # Verify CWE mapping coverage
    assert {"CWE-78", "CWE-89", "CWE-94", "CWE-502"}.issubset(cwe_ids)


@pytest.mark.asyncio
async def test_sast_runner_detects_all_vulnerable_ts_patterns():
    """Verify ESLint SAST runner detects eval(), innerHTML, and dangerouslySetInnerHTML in TypeScript/React."""
    req = SASTRunnerRequest(
        repo_id="synth-vuln-repo",
        code_snippet=SYNTHETIC_VULNERABLE_TS_COMPONENT,
        target_path="frontend/UserCommentPreview.tsx",
        tools=[SASTTool.ESLINT],
    )
    res = await sast_runner_service.run_scan(req)

    assert res.total_alerts >= 2
    rule_ids = {a.rule_id for a in res.alerts}
    cwe_ids = {a.cwe_id for a in res.alerts if a.cwe_id}

    assert "no-eval" in rule_ids
    assert "react/no-danger" in rule_ids
    assert {"CWE-79", "CWE-95"}.issubset(cwe_ids)


# ============================================================================
# 2. End-to-End Security Audit Agent Recall & OWASP Coverage Tests
# ============================================================================


@pytest.mark.asyncio
async def test_security_agent_full_owasp_cwe_recall_on_synthetic_python():
    """Verify SecurityAgentService detects SQLi, RCE, Weak Crypto, Deserialization, Path Traversal, and Secrets."""
    req = SecurityAuditRequest(
        repo_id="synth-vuln-repo",
        code_snippet=SYNTHETIC_VULNERABLE_PYTHON_APP,
        target_path="backend/vulnerable_service.py",
    )
    res = await security_agent_service.audit_security(req)

    assert res.total_vulnerabilities >= 7
    assert res.critical_count >= 4

    cwe_ids = {v.cwe_id for v in res.vulnerabilities}
    owasp_cats = {v.owasp_category for v in res.vulnerabilities}

    # Verify detection across major CWE classes
    expected_cwes = {
        "CWE-89",   # SQL Injection
        "CWE-78",   # OS Command Injection
        "CWE-94",   # Code Injection (eval/exec)
        "CWE-328",  # Weak MD5 Hash
        "CWE-502",  # Insecure Deserialization (pickle/yaml)
        "CWE-22",   # Path Traversal
    }
    assert expected_cwes.issubset(cwe_ids)

    # Verify OWASP Top 10 category mapping
    assert OWASPCategory.A03_INJECTION in owasp_cats
    assert OWASPCategory.A02_CRYPTOGRAPHIC_FAILURES in owasp_cats
    assert OWASPCategory.A08_SOFTWARE_DATA_INTEGRITY in owasp_cats
    assert OWASPCategory.A01_BROKEN_ACCESS_CONTROL in owasp_cats

    # Verify every finding has non-empty remediation and valid line citations
    for vuln in res.vulnerabilities:
        assert len(vuln.remediation.strip()) >= 15
        assert vuln.line_number >= 1
        assert (vuln.end_line_number or vuln.line_number) >= vuln.line_number
        assert vuln.confidence >= 0.5


@pytest.mark.asyncio
async def test_security_agent_detects_xss_and_eval_in_ts_component():
    """Verify SecurityAgentService detects DOM XSS and dynamic eval in frontend TypeScript components."""
    req = SecurityAuditRequest(
        repo_id="synth-vuln-repo",
        code_snippet=SYNTHETIC_VULNERABLE_TS_COMPONENT,
        target_path="frontend/UserCommentPreview.tsx",
    )
    res = await security_agent_service.audit_security(req)

    assert res.total_vulnerabilities >= 2
    cwe_ids = {v.cwe_id for v in res.vulnerabilities}
    assert "CWE-79" in cwe_ids
    assert "CWE-94" in cwe_ids or "CWE-95" in cwe_ids


# ============================================================================
# 3. End-to-End Bug Detection Agent Recall Tests
# ============================================================================


@pytest.mark.asyncio
async def test_bug_agent_detects_all_runtime_defects_in_synthetic_python():
    """Verify BugAgentService detects mutable default, bare except, dead code, builtin shadowing, and == None."""
    req = BugHuntRequest(
        repo_id="synth-vuln-repo",
        code_snippet=SYNTHETIC_VULNERABLE_PYTHON_APP,
        target_path="backend/vulnerable_service.py",
    )
    res = await bug_agent_service.hunt_bugs(req)

    assert res.total_bugs >= 5
    rule_ids = {f.rule_id for f in res.findings}

    expected_bug_rules = {
        "DEV-BUG-001",  # Bare except block
        "DEV-BUG-002",  # Mutable default argument
        "DEV-BUG-003",  # Unreachable dead code after return
        "DEV-BUG-005",  # Built-in shadowing (`id`)
        "DEV-BUG-006",  # Comparison to None using ==
    }
    assert expected_bug_rules.issubset(rule_ids)

    # Verify every bug finding includes prescriptive remediation
    for finding in res.findings:
        assert len(finding.remediation.strip()) >= 15
        assert finding.line_number >= 1


# ============================================================================
# 4. Zero False-Positive Verification on Hardened Codebase
# ============================================================================


@pytest.mark.asyncio
async def test_zero_false_positives_on_hardened_python_module():
    """Verify SAST runner, Security agent, and Bug agent produce 0 false positives on hardened production code."""
    sast_res = await sast_runner_service.run_scan(
        SASTRunnerRequest(
            repo_id="hardened-repo",
            code_snippet=SYNTHETIC_HARDENED_PYTHON_MODULE,
            target_path="backend/hardened_service.py",
            tools=[SASTTool.BANDIT, SASTTool.SEMGREP],
        )
    )
    assert sast_res.total_alerts == 0

    sec_res = await security_agent_service.audit_security(
        SecurityAuditRequest(
            repo_id="hardened-repo",
            code_snippet=SYNTHETIC_HARDENED_PYTHON_MODULE,
            target_path="backend/hardened_service.py",
        )
    )
    assert sec_res.total_vulnerabilities == 0
    assert sec_res.critical_count == 0
    assert sec_res.high_count == 0

    bug_res = await bug_agent_service.hunt_bugs(
        BugHuntRequest(
            repo_id="hardened-repo",
            code_snippet=SYNTHETIC_HARDENED_PYTHON_MODULE,
            target_path="backend/hardened_service.py",
        )
    )
    assert bug_res.total_bugs == 0


# ============================================================================
# 5. Cross-Engine Correlation & Unified Full-Audit Pipeline Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cross_engine_cwe_correlation_between_sast_and_security_agent():
    """Verify SASTNormalizedAlert CWEs align with SecurityAgentService CWEs on the same vulnerable file."""
    sast_res = await sast_runner_service.run_scan(
        SASTRunnerRequest(
            repo_id="synth-vuln-repo",
            code_snippet=SYNTHETIC_VULNERABLE_PYTHON_APP,
            target_path="backend/vulnerable_service.py",
            tools=[SASTTool.BANDIT, SASTTool.SEMGREP],
        )
    )
    sec_res = await security_agent_service.audit_security(
        SecurityAuditRequest(
            repo_id="synth-vuln-repo",
            code_snippet=SYNTHETIC_VULNERABLE_PYTHON_APP,
            target_path="backend/vulnerable_service.py",
        )
    )

    sast_cwes = {a.cwe_id for a in sast_res.alerts if a.cwe_id}
    sec_cwes = {v.cwe_id for v in sec_res.vulnerabilities}

    # All 4 core SAST CWEs (SQLi, Command Injection, Code Execution, Deserialization) must be corroborated
    overlapping_cwes = sast_cwes.intersection(sec_cwes)
    assert {"CWE-78", "CWE-89", "CWE-94", "CWE-502"}.issubset(overlapping_cwes)


def test_full_audit_endpoint_grades_vulnerable_vs_hardened_codebase():
    """Verify POST /api/v1/scans/full-audit/{repo_id} grades vulnerable code 'D'/'F' and hardened code 'A'."""
    # 1. Vulnerable codebase full audit
    vuln_resp = client.post(
        "/api/v1/scans/full-audit/synth-vuln-repo",
        json={
            "target_path": "backend/vulnerable_service.py",
            "code_snippet": SYNTHETIC_VULNERABLE_PYTHON_APP,
        },
    )
    assert vuln_resp.status_code == 200
    vuln_data = vuln_resp.json()
    assert vuln_data["health_grade"] in ("D", "F")
    assert vuln_data["risk_score"] >= 70
    assert vuln_data["total_sast_alerts"] >= 5
    assert vuln_data["total_vulnerabilities"] >= 7
    assert vuln_data["total_bugs"] >= 5

    # 2. Hardened codebase full audit
    clean_resp = client.post(
        "/api/v1/scans/full-audit/hardened-repo",
        json={
            "target_path": "backend/hardened_service.py",
            "code_snippet": SYNTHETIC_HARDENED_PYTHON_MODULE,
        },
    )
    assert clean_resp.status_code == 200
    clean_data = clean_resp.json()
    assert clean_data["health_grade"] == "A"
    assert clean_data["risk_score"] == 0
    assert clean_data["total_sast_alerts"] == 0
    assert clean_data["total_vulnerabilities"] == 0
    assert clean_data["total_bugs"] == 0


def test_full_audit_pipeline_with_multi_file_repository_retrieval():
    """Verify full-audit endpoint retrieves multi-file repository chunks when no inline snippet is passed."""
    mock_retrieval = HybridSearchResponse(
        repo_id="multi-file-repo",
        query="security audit vulnerabilities auth sql crypto",
        total_results=2,
        chunks=[
            RetrievedChunk(
                chunk_id="chunk-py-1",
                file_path="backend/vulnerable_service.py",
                symbol_name="authenticate_user",
                start_line=10,
                end_line=22,
                content=SYNTHETIC_VULNERABLE_PYTHON_APP,
                combined_score=0.96,
                dense_score=0.95,
                sparse_score=0.97,
                citation_label="backend/vulnerable_service.py:10-22",
            ),
            RetrievedChunk(
                chunk_id="chunk-ts-1",
                file_path="frontend/UserCommentPreview.tsx",
                symbol_name="UserCommentPreview",
                start_line=1,
                end_line=20,
                content=SYNTHETIC_VULNERABLE_TS_COMPONENT,
                combined_score=0.91,
                dense_score=0.90,
                sparse_score=0.92,
                citation_label="frontend/UserCommentPreview.tsx:1-20",
            ),
        ],
    )

    with patch(
        "app.services.hybrid_retriever.hybrid_retriever_service.search",
        new_callable=AsyncMock,
        return_value=mock_retrieval,
    ):
        resp = client.post(
            "/api/v1/scans/full-audit/multi-file-repo",
            json={"query": "security audit vulnerabilities auth sql crypto"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["repo_id"] == "multi-file-repo"
        assert body["total_vulnerabilities"] >= 7
        assert body["total_bugs"] >= 5
        assert body["health_grade"] in ("D", "F")
