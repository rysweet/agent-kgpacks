"""Article-related models."""

from datetime import datetime

from pydantic import BaseModel, Field


class Section(BaseModel):
    """Article section."""

    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    word_count: int = Field(..., description="Section word count")
    level: int = Field(..., description="Section heading level")


class Article(BaseModel):
    """Basic article information."""

    title: str = Field(..., description="Article title")
    category: str | None = Field(None, description="Article category")
    word_count: int = Field(..., description="Article word count")


class ArticleDetail(BaseModel):
    """Detailed article information."""

    title: str = Field(..., description="Article title")
    category: str | None = Field(None, description="Article category")
    word_count: int = Field(..., description="Article word count")
    sections: list[Section] = Field(..., description="Article sections")
    links: list[str] = Field(..., description="Outgoing links")
    backlinks: list[str] = Field(..., description="Incoming links")
    categories: list[str] = Field(..., description="Article categories")
    wikipedia_url: str = Field(..., description="Wikipedia URL")
    last_updated: datetime = Field(..., description="Last update timestamp")


class CategoryInfo(BaseModel):
    """Category information."""

    name: str = Field(..., description="Category name")
    article_count: int = Field(..., description="Number of articles")


class CategoryListResponse(BaseModel):
    """Response for categories endpoint."""

    categories: list[CategoryInfo] = Field(..., description="List of categories")
    total: int = Field(..., description="Total number of categories")


class StatsResponse(BaseModel):
    """Response for stats endpoint."""

    articles: dict = Field(..., description="Article statistics")
    sections: dict = Field(..., description="Section statistics")
    links: dict = Field(..., description="Link statistics")
    database: dict = Field(..., description="Database information")
    performance: dict | None = Field(
        default=None, description="Performance metrics (populated when available)"
    )
