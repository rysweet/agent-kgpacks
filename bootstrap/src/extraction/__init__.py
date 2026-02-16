"""Knowledge extraction from Wikipedia articles."""

from .llm_extractor import Entity, ExtractionResult, LLMExtractor, Relationship, get_extractor

__all__ = ["LLMExtractor", "Entity", "Relationship", "ExtractionResult", "get_extractor"]
