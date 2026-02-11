"""Graph data models."""

from pydantic import BaseModel, Field


class Node(BaseModel):
    """Graph node representing an article."""

    id: str = Field(..., description="Node ID (article title)")
    title: str = Field(..., description="Article title")
    category: str | None = Field(None, description="Article category")
    word_count: int = Field(..., description="Article word count")
    depth: int = Field(..., description="Depth from seed node")
    links_count: int = Field(..., description="Number of outgoing links")
    summary: str = Field("", description="Article summary")


class Edge(BaseModel):
    """Graph edge representing a link between articles."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: str = Field("internal", description="Edge type")
    weight: float = Field(1.0, description="Edge weight")


class GraphResponse(BaseModel):
    """Response for graph data endpoint."""

    seed: str = Field(..., description="Seed article title")
    nodes: list[Node] = Field(..., description="Graph nodes")
    edges: list[Edge] = Field(..., description="Graph edges")
    total_nodes: int = Field(..., description="Total number of nodes")
    total_edges: int = Field(..., description="Total number of edges")
    execution_time_ms: float = Field(..., description="Query execution time in milliseconds")
