from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class DocFormat(str, Enum):
    """Supported docstring and documentation formats."""
    GOOGLE = "google"
    SPHINX = "sphinx"
    JSDOC = "jsdoc"
    MARKDOWN = "markdown"


class MermaidDiagramType(str, Enum):
    """Supported Mermaid diagram notations."""
    FLOWCHART = "flowchart"
    SEQUENCE = "sequenceDiagram"
    CLASS = "classDiagram"


class ModuleDocItem(BaseModel):
    """Synthesized documentation entry for a single class, function, or method."""

    symbol_name: str = Field(..., description="Name of the documented symbol")
    symbol_type: str = Field(
        ..., description="Type of symbol: 'class', 'function', 'async_function', or 'method'"
    )
    signature: str = Field(..., description="Full function or class signature")
    generated_docstring: str = Field(
        ..., description="Formatted docstring (Google/Sphinx/JSDoc)"
    )
    summary: str = Field(
        ..., description="Concise plain-English explanation of purpose and behavior"
    )


class DocGenRequest(BaseModel):
    """Request payload for living documentation and Mermaid diagram generation."""

    repo_id: str = Field(..., description="Repository identifier")
    query: Optional[str] = Field(
        default=None, description="Developer prompt e.g. 'Document the authentication flow and draw a diagram'"
    )
    target_path: Optional[str] = Field(
        default=None, description="Optional file path to document"
    )
    code_snippet: Optional[str] = Field(
        default=None, description="Direct source code snippet to document"
    )
    doc_format: DocFormat = Field(
        default=DocFormat.GOOGLE, description="Preferred docstring standard"
    )
    include_mermaid: bool = Field(
        default=True, description="Whether to synthesize an architectural Mermaid diagram"
    )
    diagram_type: MermaidDiagramType = Field(
        default=MermaidDiagramType.FLOWCHART,
        description="Type of Mermaid diagram to generate",
    )


class DocGenResponse(BaseModel):
    """Comprehensive living documentation and diagram response."""

    repo_id: str
    target_file: str = Field(..., description="Primary documented file or module")
    doc_format: DocFormat
    module_overview: str = Field(
        ..., description="High-level architectural summary of the module"
    )
    documented_symbols: List[ModuleDocItem] = Field(
        default_factory=list, description="List of documented classes and functions"
    )
    mermaid_diagram: Optional[str] = Field(
        default=None, description="Valid Mermaid diagram code block"
    )
    markdown_documentation: str = Field(
        ..., description="Complete Markdown documentation ready for README or Wiki"
    )
    model_used: str = Field(
        default="ast-doc-synthesizer",
        description="Synthesis engine or LLM model used",
    )
