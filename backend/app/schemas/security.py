from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class VulnerabilitySeverity(str, Enum):
    """Severity ratings mapped to CVSS scoring bands."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class OWASPCategory(str, Enum):
    """OWASP Top 10 (2021) standard categorization."""
    A01_BROKEN_ACCESS_CONTROL = "A01:2021-Broken Access Control"
    A02_CRYPTOGRAPHIC_FAILURES = "A02:2021-Cryptographic Failures"
    A03_INJECTION = "A03:2021-Injection"
    A04_INSECURE_DESIGN = "A04:2021-Insecure Design"
    A05_SECURITY_MISCONFIGURATION = "A05:2021-Security Misconfiguration"
    A06_VULNERABLE_COMPONENTS = "A06:2021-Vulnerable and Outdated Components"
    A07_IDENTIFICATION_FAILURES = "A07:2021-Identification and Authentication Failures"
    A08_SOFTWARE_DATA_INTEGRITY = "A08:2021-Software and Data Integrity Failures"
    A09_LOGGING_FAILURES = "A09:2021-Security Logging and Monitoring Failures"
    A10_SSRF = "A10:2021-Server-Side Request Forgery (SSRF)"


class SecurityVulnerability(BaseModel):
    """Detailed record of an identified security vulnerability."""

    rule_id: str = Field(
        ...,
        description="Vulnerability rule identifier e.g. SEC-INJ-001",
        examples=["SEC-INJ-001"],
    )
    cwe_id: str = Field(
        ...,
        description="Common Weakness Enumeration ID e.g. CWE-89",
        examples=["CWE-89"],
    )
    owasp_category: OWASPCategory = Field(
        ..., description="Mapped OWASP Top 10 category"
    )
    title: str = Field(..., description="Vulnerability title")
    description: str = Field(
        ..., description="Technical explanation of the security risk and exploitability"
    )
    severity: VulnerabilitySeverity = Field(
        ..., description="Risk severity rating"
    )
    file_path: str = Field(..., description="Source file containing the vulnerability")
    line_number: int = Field(..., description="1-indexed line number")
    end_line_number: Optional[int] = Field(
        default=None, description="Ending line number of vulnerable block"
    )
    code_snippet: str = Field(..., description="Vulnerable code snippet")
    remediation: str = Field(
        ..., description="Prescriptive remediation guidance and secure coding fix"
    )
    confidence: float = Field(
        default=0.95, ge=0.0, le=1.0, description="Confidence score of detection"
    )


class SecurityAuditRequest(BaseModel):
    """Request payload for security auditing."""

    repo_id: str = Field(..., description="Repository identifier")
    query: Optional[str] = Field(
        default=None, description="Security focus e.g. 'audit SQL queries' or 'check auth flow'"
    )
    code_snippet: Optional[str] = Field(
        default=None, description="Direct code snippet to audit"
    )
    target_path: Optional[str] = Field(
        default=None, description="Target file path to inspect"
    )
    severity_filter: Optional[List[VulnerabilitySeverity]] = Field(
        default=None, description="Optional filter for specific severity levels"
    )


class SecurityAuditResponse(BaseModel):
    """Comprehensive SAST security report."""

    repo_id: str
    total_vulnerabilities: int = Field(
        default=0, description="Total security findings count"
    )
    critical_count: int = Field(default=0)
    high_count: int = Field(default=0)
    medium_count: int = Field(default=0)
    low_count: int = Field(default=0)
    vulnerabilities: List[SecurityVulnerability] = Field(
        default_factory=list, description="List of detected vulnerabilities"
    )
    summary: str = Field(..., description="Narrative executive summary of security posture")
    model_used: str = Field(
        default="sast-pattern-analyzer",
        description="Analysis engine or LLM model used for the audit",
    )
