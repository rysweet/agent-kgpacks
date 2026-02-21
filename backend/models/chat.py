"""Chat request and response models."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    question: str = Field(
        ..., min_length=1, max_length=500, description="Natural language question"
    )
    max_results: int = Field(10, ge=1, le=50, description="Maximum graph results to retrieve")


class ChatResponse(BaseModel):
    """Response body for the chat endpoint."""

    answer: str = Field(..., description="Natural language answer from the agent")
    sources: list[str] = Field(default_factory=list, description="Source article titles")
    query_type: str = Field(..., description="Classified query type (e.g. entity_search)")
    execution_time_ms: float = Field(..., description="Total request time in milliseconds")
