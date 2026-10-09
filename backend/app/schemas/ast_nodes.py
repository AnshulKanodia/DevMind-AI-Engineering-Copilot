from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class CodeSymbolType(str, Enum):
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    STRUCT = "struct"
    MODULE = "module"
    BLOCK = "block"


class ParsedCodeSymbol(BaseModel):
    name: str = Field(..., description="Symbol name (e.g., function name, class name)")
    symbol_type: CodeSymbolType = Field(..., description="Categorization of the code symbol")
    start_line: int = Field(..., description="1-indexed starting line number in source file")
    end_line: int = Field(..., description="1-indexed ending line number in source file")
    signature: Optional[str] = Field(None, description="Signature/header definition line")
    docstring: Optional[str] = Field(None, description="Extracted docstring or leading comment")
    body_text: str = Field(..., description="Exact source code block spanning start_line to end_line")
    parent_symbol: Optional[str] = Field(None, description="Enclosing class or parent scope if nested")


class ParsedFileAST(BaseModel):
    file_path: str = Field(..., description="Relative file path within repository")
    language: str = Field(..., description="Detected programming language")
    total_symbols: int = Field(..., description="Total extracted logical code symbols")
    total_lines: int = Field(..., description="Total line count in source file")
    symbols: List[ParsedCodeSymbol] = Field(default_factory=list, description="Extracted symbols")
