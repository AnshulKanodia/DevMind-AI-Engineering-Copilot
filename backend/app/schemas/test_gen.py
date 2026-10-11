from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class TestFramework(str, Enum):
    """Supported unit testing frameworks across languages."""
    __test__ = False
    PYTEST = "pytest"
    UNITTEST = "unittest"
    JEST = "jest"
    VITEST = "vitest"
    GO_TEST = "go_test"
    JUNIT = "junit"


class GeneratedTestCase(BaseModel):
    """Individual synthesized unit test case."""

    test_name: str = Field(
        ...,
        description="Name of the test function or spec e.g. 'test_calculate_tax_happy_path'",
    )
    category: str = Field(
        ...,
        description="Test classification: 'happy_path', 'edge_case', 'error_handling', or 'mock_isolation'",
    )
    description: str = Field(
        ..., description="What behavior or condition this test case verifies"
    )
    test_code: str = Field(..., description="Runnable test case code block")
    mocked_dependencies: List[str] = Field(
        default_factory=list,
        description="External calls or dependencies mocked within this test",
    )


class TestGenRequest(BaseModel):
    """Request payload for automated unit test generation."""
    __test__ = False

    repo_id: str = Field(..., description="Repository identifier")
    query: Optional[str] = Field(
        default=None, description="Developer prompt e.g. 'Generate unit tests for process_payment'"
    )
    target_symbol: Optional[str] = Field(
        default=None, description="Specific function, method, or class name to test"
    )
    target_path: Optional[str] = Field(
        default=None, description="File path containing the target symbol"
    )
    code_snippet: Optional[str] = Field(
        default=None, description="Direct source code snippet to synthesize tests for"
    )
    framework: Optional[TestFramework] = Field(
        default=None, description="Preferred testing framework (auto-detected if omitted)"
    )


class TestGenResponse(BaseModel):
    """Comprehensive generated unit test suite response."""
    __test__ = False

    repo_id: str
    framework: TestFramework = Field(
        ..., description="Testing framework used for synthesis"
    )
    target_symbol: str = Field(..., description="Primary symbol under test")
    target_file: str = Field(..., description="Source file path of the tested code")
    total_tests: int = Field(default=0, description="Total number of test cases generated")
    test_cases: List[GeneratedTestCase] = Field(
        default_factory=list, description="Structured breakdown of generated test cases"
    )
    full_test_suite_code: str = Field(
        ..., description="Complete, ready-to-run test file source code"
    )
    summary: str = Field(
        ..., description="Markdown report detailing test coverage and mock strategy"
    )
    model_used: str = Field(
        default="ast-test-synthesizer",
        description="Synthesis engine or LLM model used",
    )
