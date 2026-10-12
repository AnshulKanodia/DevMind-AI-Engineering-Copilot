from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SASTTool(str, Enum):
    """Supported static analysis & linter engines."""
    BANDIT = "bandit"
    SEMGREP = "semgrep"
    ESLINT = "eslint"


class SASTNormalizedAlert(BaseModel):
    """Standardized diagnostic alert normalized across Bandit, Semgrep, and ESLint."""

    tool: SASTTool = Field(..., description="Source SAST tool that emitted the alert")
    rule_id: str = Field(..., description="Tool-specific rule ID e.g. 'B301', 'no-eval'")
    severity: str = Field(
        ..., description="Normalized severity: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'"
    )
    confidence: str = Field(
        default="HIGH", description="Confidence rating: 'HIGH', 'MEDIUM', or 'LOW'"
    )
    message: str = Field(..., description="Diagnostic description of the issue")
    file_path: str = Field(..., description="Relative file path")
    line_number: int = Field(..., description="1-indexed line number")
    code_snippet: Optional[str] = Field(default=None, description="Flagged source line")
    cwe_id: Optional[str] = Field(default=None, description="Mapped CWE identifier if available")


class SASTRunnerRequest(BaseModel):
    """Request payload for executing isolated SAST scans."""

    repo_id: str = Field(..., description="Repository identifier")
    target_path: Optional[str] = Field(
        default=None, description="Relative file path within repository or snippet filename"
    )
    code_snippet: Optional[str] = Field(
        default=None, description="Optional source code snippet to scan in an ephemeral file"
    )
    tools: List[SASTTool] = Field(
        default_factory=lambda: [SASTTool.BANDIT, SASTTool.SEMGREP, SASTTool.ESLINT],
        description="List of SAST linters to execute",
    )
    timeout_seconds: int = Field(
        default=15, ge=1, le=60, description="Strict per-tool execution timeout in seconds"
    )


class SASTRunnerResponse(BaseModel):
    """Consolidated SAST execution report."""

    repo_id: str
    executed_tools: List[str] = Field(
        default_factory=list, description="Tools executed during the scan"
    )
    total_alerts: int = Field(default=0, description="Total normalized alerts")
    alerts: List[SASTNormalizedAlert] = Field(
        default_factory=list, description="Normalized alerts across all tools"
    )
    execution_time_ms: float = Field(
        default=0.0, description="Total execution duration in milliseconds"
    )
    timed_out: bool = Field(
        default=False, description="Whether any underlying tool exceeded its timeout"
    )


class FullRepoAuditRequest(BaseModel):
    """Request payload for combined SAST, bug detection, and OWASP security audit."""

    target_path: Optional[str] = Field(
        default=None, description="Optional single file path filter"
    )
    code_snippet: Optional[str] = Field(
        default=None, description="Optional code snippet to audit directly"
    )
    query: Optional[str] = Field(
        default=None, description="Optional focus query for repository vector retrieval"
    )


class FullRepoAuditResponse(BaseModel):
    """Unified repository health, bug, and security audit report."""

    repo_id: str
    risk_score: int = Field(
        ..., ge=0, le=100, description="Composite risk score (0 = clean, 100 = critical risk)"
    )
    health_grade: str = Field(
        ..., description="Overall codebase security & reliability grade ('A' through 'F')"
    )
    total_sast_alerts: int = Field(default=0)
    total_bugs: int = Field(default=0)
    total_vulnerabilities: int = Field(default=0)
    sast_alerts: List[SASTNormalizedAlert] = Field(default_factory=list)
    bug_summary: str = Field(default="")
    security_summary: str = Field(default="")

