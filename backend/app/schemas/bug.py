from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class BugSeverity(str, Enum):
    """Severity classification for detected code bugs and anti-patterns."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class BugFinding(BaseModel):
    """Detailed record of a detected software bug, anti-pattern, or runtime hazard."""

    rule_id: str = Field(
        ...,
        description="Rule identifier e.g. 'DEV-BUG-001'",
        examples=["DEV-BUG-001"],
    )
    title: str = Field(..., description="Concise headline describing the defect")
    description: str = Field(
        ..., description="Technical explanation of the defect and potential failure mode"
    )
    severity: BugSeverity = Field(..., description="Impact severity of the finding")
    file_path: str = Field(..., description="File path relative to repository root")
    line_number: int = Field(..., description="1-indexed line where defect originates")
    end_line_number: Optional[int] = Field(
        default=None, description="Ending line if defect spans a block"
    )
    code_snippet: str = Field(..., description="Problematic code snippet excerpt")
    remediation: str = Field(
        ..., description="Prescriptive guidance or patch to fix the defect"
    )
    confidence: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Detection confidence score"
    )
    symbol_name: Optional[str] = Field(
        default=None, description="Enclosing function or class name if applicable"
    )


class BugHuntRequest(BaseModel):
    """Request payload for automated bug diagnosis."""

    repo_id: str = Field(..., description="Repository identifier")
    query: Optional[str] = Field(
        default=None, description="Optional developer question or symptom description"
    )
    target_path: Optional[str] = Field(
        default=None, description="Optional target file path to analyze"
    )
    code_snippet: Optional[str] = Field(
        default=None, description="Direct code snippet to analyze without repo context"
    )
    severity_filter: Optional[List[BugSeverity]] = Field(
        default=None, description="Optional list of severities to include"
    )


class BugHuntResponse(BaseModel):
    """Comprehensive diagnostic bug hunting report."""

    repo_id: str
    total_bugs: int = Field(default=0, description="Total number of findings identified")
    critical_count: int = Field(default=0)
    high_count: int = Field(default=0)
    medium_count: int = Field(default=0)
    low_count: int = Field(default=0)
    findings: List[BugFinding] = Field(
        default_factory=list, description="Ordered list of bug findings"
    )
    summary: str = Field(..., description="High-level narrative summarizing findings")
    model_used: str = Field(
        default="ast-static-analyzer",
        description="Analyzer engine or LLM model used for diagnosis",
    )
