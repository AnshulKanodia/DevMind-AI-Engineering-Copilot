from typing import List
from pydantic import BaseModel, Field

from app.agents.state import AgentIntent


class RouterClassificationResult(BaseModel):
    intent: AgentIntent = Field(..., description="Classified intent for agent delegation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Routing confidence score")
    reasoning: str = Field(..., description="Brief architectural reasoning behind this delegation")
    extracted_keywords: List[str] = Field(default_factory=list, description="Key technical identifiers detected")
    target_subagent: str = Field(..., description="Human-readable subagent title")
    suggested_search_queries: List[str] = Field(
        default_factory=list, description="Derived queries optimized for hybrid code retrieval"
    )
