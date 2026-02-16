"""
LLM-based knowledge extraction from Wikipedia articles.

Uses Claude (Anthropic API) to extract:
- Named entities (people, places, organizations, concepts)
- Relationships between entities
- Key facts and properties

This transforms raw Wikipedia text into structured knowledge graph entries.
"""

import json
import logging
import os
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Extracted entity with type and properties."""

    name: str
    type: str  # person, place, organization, concept, event
    properties: dict  # key-value pairs


@dataclass
class Relationship:
    """Relationship between two entities."""

    source: str
    relation: str
    target: str
    context: str  # sentence/clause where relationship appears


@dataclass
class ExtractionResult:
    """Complete extraction from an article."""

    entities: list[Entity]
    relationships: list[Relationship]
    key_facts: list[str]


class LLMExtractor:
    """Extract structured knowledge from text using Claude."""

    def __init__(self, model: str = "claude-3-5-haiku-20241022"):
        """Initialize with Anthropic API key from environment."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        logger.info(f"LLM Extractor initialized with model: {model}")

    def extract_from_article(
        self, title: str, sections: list[dict], max_sections: int = 5
    ) -> ExtractionResult:
        """
        Extract entities and relationships from Wikipedia article.

        Args:
            title: Article title
            sections: Parsed sections from Wikipedia (from parser.py)
            max_sections: Limit sections to process (cost control)

        Returns:
            ExtractionResult with entities, relationships, and facts
        """
        # Take first N sections (usually intro + main sections)
        content_sections = sections[:max_sections]
        combined_text = f"# {title}\n\n"
        for s in content_sections:
            section_title = s.get("title", "")
            section_content = s.get("content", "")
            if section_title:
                combined_text += f"## {section_title}\n{section_content}\n\n"
            else:
                combined_text += f"{section_content}\n\n"

        # Truncate to 8K chars (~2K tokens) to keep costs reasonable
        if len(combined_text) > 8000:
            combined_text = combined_text[:8000] + "...[truncated]"

        prompt = f"""Extract structured knowledge from this Wikipedia article.

Article text:
{combined_text}

Extract:
1. **Entities**: Named entities with their type (person/place/organization/concept/event)
2. **Relationships**: Connections between entities (who did what, what caused what, etc.)
3. **Key Facts**: 3-5 most important facts about the main topic

Return JSON in this format:
{{
  "entities": [
    {{"name": "Entity Name", "type": "person|place|org|concept|event", "properties": {{"key": "value"}}}},
    ...
  ],
  "relationships": [
    {{"source": "Entity A", "relation": "founded", "target": "Entity B", "context": "sentence where this appears"}},
    ...
  ],
  "key_facts": [
    "Fact 1",
    "Fact 2",
    ...
  ]
}}

Focus on the most important entities and relationships. Be concise."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)

            entities = [
                Entity(
                    name=e["name"],
                    type=e.get("type", "concept"),
                    properties=e.get("properties", {}),
                )
                for e in data.get("entities", [])
            ]

            relationships = [
                Relationship(
                    source=r["source"],
                    relation=r.get("relation", "related_to"),
                    target=r["target"],
                    context=r.get("context", ""),
                )
                for r in data.get("relationships", [])
            ]

            key_facts = data.get("key_facts", [])

            logger.info(
                f"  Extracted: {len(entities)} entities, "
                f"{len(relationships)} relationships, {len(key_facts)} facts"
            )

            return ExtractionResult(
                entities=entities, relationships=relationships, key_facts=key_facts
            )

        except Exception as e:
            logger.error(f"  LLM extraction failed: {e}")
            # Return empty result on failure
            return ExtractionResult(entities=[], relationships=[], key_facts=[])


# Singleton instance
_extractor = None


def get_extractor() -> LLMExtractor:
    """Get or create singleton LLM extractor."""
    global _extractor
    if _extractor is None:
        _extractor = LLMExtractor()
    return _extractor
