from fastapi import APIRouter

from app.schemas.bug import BugHuntRequest, BugHuntResponse
from app.schemas.sast import (
    FullRepoAuditRequest,
    FullRepoAuditResponse,
    SASTRunnerRequest,
    SASTRunnerResponse,
)
from app.schemas.security import SecurityAuditRequest, SecurityAuditResponse
from app.services.bug_agent import bug_agent_service
from app.services.sast_runner import sast_runner_service
from app.services.security_agent import security_agent_service

router = APIRouter()


@router.post("/sast", response_model=SASTRunnerResponse)
async def trigger_sast_scan(request: SASTRunnerRequest) -> SASTRunnerResponse:
    """Run isolated SAST linters (Bandit, Semgrep, ESLint) on repository or snippet."""
    return await sast_runner_service.run_scan(request)


@router.post("/bugs", response_model=BugHuntResponse)
async def trigger_bug_scan(request: BugHuntRequest) -> BugHuntResponse:
    """Run AST and semantic bug detection across repository or code snippet."""
    return await bug_agent_service.hunt_bugs(request)


@router.post("/security", response_model=SecurityAuditResponse)
async def trigger_security_scan(request: SecurityAuditRequest) -> SecurityAuditResponse:
    """Run OWASP Top 10 and CWE vulnerability audit on repository or code snippet."""
    return await security_agent_service.audit_security(request)


@router.post("/full-audit/{repo_id}", response_model=FullRepoAuditResponse)
async def trigger_full_repository_audit(
    repo_id: str,
    request: FullRepoAuditRequest,
) -> FullRepoAuditResponse:
    """Execute combined SAST, bug detection, and security audit with risk scoring."""
    sast_req = SASTRunnerRequest(
        repo_id=repo_id,
        target_path=request.target_path,
        code_snippet=request.code_snippet,
    )
    bug_req = BugHuntRequest(
        repo_id=repo_id,
        query=request.query,
        target_path=request.target_path,
        code_snippet=request.code_snippet,
    )
    sec_req = SecurityAuditRequest(
        repo_id=repo_id,
        query=request.query,
        target_path=request.target_path,
        code_snippet=request.code_snippet,
    )

    sast_resp = await sast_runner_service.run_scan(sast_req)
    bug_resp = await bug_agent_service.hunt_bugs(bug_req)
    sec_resp = await security_agent_service.audit_security(sec_req)

    # Calculate composite risk score (0 to 100)
    raw_risk = (
        sec_resp.critical_count * 25
        + sec_resp.high_count * 15
        + bug_resp.critical_count * 20
        + bug_resp.high_count * 10
        + sast_resp.total_alerts * 5
        + (sec_resp.medium_count + bug_resp.medium_count) * 5
        + (sec_resp.low_count + bug_resp.low_count) * 2
    )
    risk_score = min(100, raw_risk)

    if risk_score == 0:
        grade = "A"
    elif risk_score <= 20:
        grade = "B"
    elif risk_score <= 45:
        grade = "C"
    elif risk_score <= 70:
        grade = "D"
    else:
        grade = "F"

    return FullRepoAuditResponse(
        repo_id=repo_id,
        risk_score=risk_score,
        health_grade=grade,
        total_sast_alerts=sast_resp.total_alerts,
        total_bugs=bug_resp.total_bugs,
        total_vulnerabilities=sec_resp.total_vulnerabilities,
        sast_alerts=sast_resp.alerts,
        bug_summary=bug_resp.summary,
        security_summary=sec_resp.summary,
    )
