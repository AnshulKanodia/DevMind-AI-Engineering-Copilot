from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CodeChunk(BaseModel):
    chunk_id: str = Field(..., description="Unique deterministic identifier for the code chunk")
    repo_id: str = Field(..., description="Repository identifier")
    file_path: str = Field(..., description="Relative file path in repository")
    symbol_name: Optional[str] = Field(None, description="Name of the function, class, or method")
    symbol_type: str = Field("code_block", description="Symbol type: function, method, class, block")
    start_line: int = Field(..., description="1-indexed starting line number")
    end_line: int = Field(..., description="1-indexed ending line number")
    content: str = Field(..., description="Source code text including contextual headers")
    token_count: int = Field(..., description="Estimated token count of the chunk content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Language, parent scope, docstring")


class ChunkingSummary(BaseModel):
    repo_id: str
    total_files_chunked: int
    total_chunks: int
    total_tokens: int
    average_chunk_size_tokens: float
    chunks: List[CodeChunk] = []
