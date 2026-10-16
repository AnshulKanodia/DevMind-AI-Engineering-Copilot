from pathlib import Path
import json
import yaml
import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
K8S_DIR = REPO_ROOT / "deploy" / "k8s"
ECS_DIR = REPO_ROOT / "deploy" / "ecs"


def test_k8s_manifests_exist_and_valid_yaml():
    """Verify all Kubernetes manifests in deploy/k8s are well-formed YAML files."""
    assert K8S_DIR.exists()
    yaml_files = list(K8S_DIR.glob("*.yaml")) + list(K8S_DIR.glob("*.yml"))
    assert len(yaml_files) >= 7

    for yf in yaml_files:
        with open(yf, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            assert len(docs) >= 1, f"Failed to parse YAML from {yf.name}"
            for doc in docs:
                if doc is not None:
                    assert "apiVersion" in doc or "resources" in doc


def test_k8s_security_hardening():
    """Verify all Deployments enforce non-root execution and drop all capabilities."""
    deployments = ["backend-deployment.yaml", "frontend-deployment.yaml"]

    for d_name in deployments:
        fpath = K8S_DIR / d_name
        assert fpath.exists()
        with open(fpath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        spec = data["spec"]["template"]["spec"]
        pod_sec = spec.get("securityContext", {})
        assert pod_sec.get("runAsNonRoot") is True
        assert pod_sec.get("runAsUser") == 10001

        for container in spec["containers"]:
            c_sec = container.get("securityContext", {})
            assert c_sec.get("allowPrivilegeEscalation") is False
            assert "ALL" in c_sec.get("capabilities", {}).get("drop", [])


def test_k8s_health_probes_and_resources():
    """Verify backend and frontend deployments configure readiness, liveness, and resource limits."""
    deployments = ["backend-deployment.yaml", "frontend-deployment.yaml"]

    for d_name in deployments:
        fpath = K8S_DIR / d_name
        with open(fpath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        containers = data["spec"]["template"]["spec"]["containers"]
        for c in containers:
            assert "readinessProbe" in c, f"Missing readinessProbe in {d_name}"
            assert "livenessProbe" in c, f"Missing livenessProbe in {d_name}"
            assert "resources" in c, f"Missing resources block in {d_name}"
            assert "requests" in c["resources"]
            assert "limits" in c["resources"]


def test_k8s_ingress_and_services():
    """Verify Ingress rules route to backend on /api and frontend on /."""
    ingress_path = K8S_DIR / "ingress.yaml"
    assert ingress_path.exists()
    with open(ingress_path, "r", encoding="utf-8") as f:
        ingress = yaml.safe_load(f)

    paths = ingress["spec"]["rules"][0]["http"]["paths"]
    path_map = {p["path"]: p["backend"]["service"]["name"] for p in paths}
    assert "/api" in path_map
    assert path_map["/api"] == "devmind-backend"
    assert "/" in path_map
    assert path_map["/"] == "devmind-frontend"


def test_ecs_task_definition():
    """Verify AWS ECS Fargate task definition syntax and container definitions."""
    ecs_file = ECS_DIR / "task-definition.json"
    assert ecs_file.exists()

    with open(ecs_file, "r", encoding="utf-8") as f:
        task_def = json.load(f)

    assert task_def["networkMode"] == "awsvpc"
    assert "FARGATE" in task_def["requiresCompatibilities"]
    assert len(task_def["containerDefinitions"]) == 2

    c_names = [c["name"] for c in task_def["containerDefinitions"]]
    assert "devmind-backend" in c_names
    assert "devmind-frontend" in c_names
