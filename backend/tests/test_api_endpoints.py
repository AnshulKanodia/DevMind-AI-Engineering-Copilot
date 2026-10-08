from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_root_and_health():
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "DevMind API"
    assert data["status"] == "operational"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


def test_api_v1_status():
    res = client.get("/api/v1/status")
    assert res.status_code == 200
    assert res.json()["status"] == "active"


def test_auth_login_url():
    res = client.get("/api/v1/auth/login?state=custom_state")
    assert res.status_code == 200
    data = res.json()
    assert "authorization_url" in data
    assert "github.com/login/oauth/authorize" in data["authorization_url"]
    assert "state=custom_state" in data["authorization_url"]


def test_auth_me_unauthorized_without_token():
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"]
