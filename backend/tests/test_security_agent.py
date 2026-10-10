import pytest
from app.agents.graph import build_devmind_graph
from app.agents.state import create_initial_state
from app.schemas.chunk import CodeChunk
from app.schemas.security import (
    OWASPCategory,
    SecurityAuditRequest,
    VulnerabilitySeverity,
)
from app.services.hybrid_retriever import hybrid_retriever_service
from app.services.security_agent import security_agent_service


def test_sql_injection_detection():
    source = """
def get_user_profile(cursor, username):
    query = f"SELECT id, email, role FROM users WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchone()
"""
    vulns = security_agent_service.analyze_source_code(source, "db/users.py")
    rule_ids = [v.rule_id for v in vulns]
    assert "SEC-INJ-001" in rule_ids

    sqli = next(v for v in vulns if v.rule_id == "SEC-INJ-001")
    assert sqli.cwe_id == "CWE-89"
    assert sqli.owasp_category == OWASPCategory.A03_INJECTION
    assert sqli.severity == VulnerabilitySeverity.CRITICAL
    assert "parameterized queries" in sqli.remediation.lower()


def test_command_injection_eval_exec():
    source = """
def evaluate_math(expression):
    return eval(expression)

def run_script(payload):
    exec(payload)
"""
    vulns = security_agent_service.analyze_source_code(source, "calc.py")
    rule_ids = [v.rule_id for v in vulns]
    assert "SEC-INJ-002" in rule_ids
    findings = [v for v in vulns if v.rule_id == "SEC-INJ-002"]
    assert len(findings) == 2
    assert findings[0].severity == VulnerabilitySeverity.CRITICAL


def test_command_injection_os_system_subprocess():
    source = """
import os
import subprocess

def ping_host(host):
    os.system(f"ping -c 1 {host}")
    subprocess.Popen(f"ping -c 1 {host}", shell=True)
"""
    vulns = security_agent_service.analyze_source_code(source, "network.py")
    rule_ids = [v.rule_id for v in vulns]
    assert "SEC-INJ-003" in rule_ids
    findings = [v for v in vulns if v.rule_id == "SEC-INJ-003"]
    assert len(findings) == 2


def test_insecure_hashing_md5_sha1():
    source = """
import hashlib

def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()

def checksum_data(data):
    return hashlib.sha1(data.encode()).hexdigest()
"""
    vulns = security_agent_service.analyze_source_code(source, "hasher.py")
    rule_ids = [v.rule_id for v in vulns]
    assert "SEC-CRYPTO-001" in rule_ids
    findings = [v for v in vulns if v.rule_id == "SEC-CRYPTO-001"]
    assert len(findings) == 2
    assert findings[0].owasp_category == OWASPCategory.A02_CRYPTOGRAPHIC_FAILURES


def test_insecure_deserialization_pickle():
    source = """
import pickle

def load_session(raw_bytes):
    return pickle.loads(raw_bytes)
"""
    vulns = security_agent_service.analyze_source_code(source, "session.py")
    rule_ids = [v.rule_id for v in vulns]
    assert "SEC-INTEG-001" in rule_ids

    pickle_vuln = next(v for v in vulns if v.rule_id == "SEC-INTEG-001")
    assert pickle_vuln.cwe_id == "CWE-502"
    assert pickle_vuln.severity == VulnerabilitySeverity.CRITICAL


def test_hardcoded_secrets_detection():
    source = """
# Production AWS configuration
AWS_SECRET = "AKIAIOSFODNN7EXAMPLE"
GITHUB_TOKEN = "ghp_111111111122222222223333333333444444"
"""
    vulns = security_agent_service.analyze_source_code(source, "config.py")
    rule_ids = [v.rule_id for v in vulns]
    assert "SEC-AUTH-001" in rule_ids
    findings = [v for v in vulns if v.rule_id == "SEC-AUTH-001"]
    assert len(findings) >= 2


def test_xss_detection():
    source = """
export function RenderRaw({ userHtml }) {
    return <div dangerouslySetInnerHTML={{ __html: userHtml }} />;
}
"""
    vulns = security_agent_service.analyze_source_code(source, "Component.tsx")
    rule_ids = [v.rule_id for v in vulns]
    assert "SEC-XSS-001" in rule_ids

    xss = next(v for v in vulns if v.rule_id == "SEC-XSS-001")
    assert xss.cwe_id == "CWE-79"
    assert xss.severity == VulnerabilitySeverity.HIGH


def test_clean_code_zero_vulnerabilities():
    source = """
import hashlib
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_and_hash(plain_pwd):
    return pwd_context.hash(plain_pwd)

def safe_query(cursor, user_id):
    cursor.execute("SELECT id FROM users WHERE id = :id", {"id": user_id})
    return cursor.fetchone()
"""
    vulns = security_agent_service.analyze_source_code(source, "auth_safe.py")
    assert len(vulns) == 0


@pytest.mark.asyncio
async def test_workflow_graph_security_node_execution():
    repo_id = "test-graph-security-repo"
    vuln_chunk = CodeChunk(
        chunk_id="chk_sec_1",
        repo_id=repo_id,
        file_path="app/api/endpoints/data.py",
        symbol_name="raw_eval_endpoint",
        start_line=15,
        end_line=25,
        content="""def raw_eval_endpoint(user_expr):
    result = eval(user_expr)
    return {"result": result}
""",
        token_count=14,
        metadata={"language": "python"},
    )
    hybrid_retriever_service.register_repo_chunks(repo_id, [vuln_chunk])

    graph = build_devmind_graph()
    initial_state = create_initial_state(
        repo_id=repo_id,
        user_query="Audit this endpoint for potential vulnerabilities, eval, and SQL injection",
    )

    final_state = await graph.execute(initial_state)

    assert final_state["current_step"] == "completed"
    assert final_state["intent"] == "security_audit"
    assert len(final_state["diagnostic_findings"]) >= 1
    assert "app/api/endpoints/data.py" in final_state["final_response"]
    assert len(final_state["citations"]) > 0
    assert final_state["metadata"]["critical_count"] >= 1
