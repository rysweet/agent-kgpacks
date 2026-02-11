"""Search-related models."""

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Single search result."""

    article: str = Field(..., description="Article title")
    similarity: float = Field(..., description="Similarity score (0.0-1.0)")
    category: str | None = Field(None, description="Article category")
    word_count: int = Field(..., description="Article word count")
    summary: str = Field("", description="Article summary")


class SearchResponse(BaseModel):
    """Response for semantic search endpoint."""

    query: str = Field(..., description="Search query")
    results: list[SearchResult] = Field(..., description="Search results")
    total: int = Field(..., description="Total number of results")
    execution_time_ms: float = Field(..., description="Query execution time in milliseconds")


class AutocompleteResult(BaseModel):
    """Single autocomplete suggestion."""

    title: str = Field(..., description="Article title")
    category: str | None = Field(None, description="Article category")
    match_type: str = Field(..., description="Type of match (prefix, contains, etc.)")


class AutocompleteResponse(BaseModel):
    """Response for autocomplete endpoint."""

    query: str = Field(..., description="Search query")
    suggestions: list[AutocompleteResult] = Field(..., description="Autocomplete suggestions")
    total: int = Field(..., description="Total number of suggestions")
