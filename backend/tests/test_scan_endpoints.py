from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_trigger_sast_scan_endpoint():
    resp = client.post(
        "/api/v1/scans/sast",
        json={
            "repo_id": "scan-api-repo",
            "target_path": "app/unsafe.py",
            "code_snippet": "import pickle\nobj = pickle.loads(data)\nres = eval(user_input)",
            "tools": ["bandit"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["repo_id"] == "scan-api-repo"
    assert body["total_alerts"] >= 2
    rule_ids = {a["rule_id"] for a in body["alerts"]}
    assert "B301" in rule_ids
    assert "B307" in rule_ids


def test_trigger_bug_scan_endpoint():
    resp = client.post(
        "/api/v1/scans/bugs",
        json={
            "repo_id": "scan-api-repo",
            "target_path": "app/handler.py",
            "code_snippet": "def process(items=[]):\n    try:\n        return items[0]\n    except:\n        pass",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_bugs"] >= 2
    rule_ids = {f["rule_id"] for f in body["findings"]}
    assert "DEV-BUG-001" in rule_ids
    assert "DEV-BUG-002" in rule_ids


def test_trigger_security_scan_endpoint():
    resp = client.post(
        "/api/v1/scans/security",
        json={
            "repo_id": "scan-api-repo",
            "target_path": "app/db_auth.py",
            "code_snippet": (
                "import hashlib\n"
                "def login(cursor, user, pwd):\n"
                "    digest = hashlib.md5(pwd.encode()).hexdigest()\n"
                "    cursor.execute(f\"SELECT * FROM users WHERE user='{user}'\")\n"
            ),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_vulnerabilities"] >= 2
    assert body["critical_count"] >= 1
    assert body["high_count"] >= 1


def test_full_repository_audit_vulnerable_code():
    resp = client.post(
        "/api/v1/scans/full-audit/audit-vuln-repo",
        json={
            "target_path": "app/legacy.py",
            "code_snippet": (
                "import os, pickle\n"
                "def run_unsafe(cmd, payload, cache=[]):\n"
                "    try:\n"
                "        os.system(cmd)\n"
                "        pickle.loads(payload)\n"
                "    except:\n"
                "        pass\n"
            ),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["repo_id"] == "audit-vuln-repo"
    assert body["risk_score"] >= 50
    assert body["health_grade"] in ("D", "F")
    assert body["total_vulnerabilities"] >= 2
    assert body["total_bugs"] >= 2
    assert body["total_sast_alerts"] >= 1


def test_full_repository_audit_clean_code():
    resp = client.post(
        "/api/v1/scans/full-audit/audit-clean-repo",
        json={
            "target_path": "app/clean_math.py",
            "code_snippet": (
                "def add_integers(a: int, b: int) -> int:\n"
                "    return a + b\n"
            ),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_score"] == 0
    assert body["health_grade"] == "A"
    assert body["total_vulnerabilities"] == 0
    assert body["total_bugs"] == 0
    assert body["total_sast_alerts"] == 0
