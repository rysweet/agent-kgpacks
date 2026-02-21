"""
WikiGR Agents.

Query and reason over the Wikipedia knowledge graph using natural language,
or generate seed articles from topics to build new knowledge graphs.
"""

from .kg_agent import KnowledgeGraphAgent
from .seed_agent import SeedAgent

__all__ = ["KnowledgeGraphAgent", "SeedAgent"]
