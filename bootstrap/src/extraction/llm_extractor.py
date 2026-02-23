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

# Standard relation types for normalization. Maps common synonyms to canonical forms.
_RELATION_SYNONYMS: dict[str, str] = {
    "established": "founded",
    "co-founded": "founded",
    "co_founded": "founded",
    "cofounded": "founded",
    "set_up": "founded",
    "built": "created",
    "made": "created",
    "constructed": "created",
    "designed": "created",
    "devised": "invented",
    "conceived": "invented",
    "patented": "invented",
    "found": "discovered",
    "uncovered": "discovered",
    "identified": "discovered",
    "built_on": "developed",
    "advanced": "developed",
    "improved": "developed",
    "refined": "developed",
    "headed": "led",
    "managed": "led",
    "chaired": "led",
    "ran": "led",
    "supervised": "directed",
    "oversaw": "directed",
    "wrote": "authored",
    "published": "authored",
    "co-authored": "authored",
    "affected": "influenced",
    "impacted": "influenced",
    "shaped": "influenced",
    "motivated": "inspired",
    "component_of": "part_of",
    "member_of": "part_of",
    "belongs_to": "part_of",
    "subset_of": "part_of",
    "employs": "uses",
    "utilizes": "uses",
    "relies_on": "requires",
    "depends_on": "requires",
    "needs": "requires",
    "led_to": "caused",
    "triggered": "caused",
    "produced": "resulted_in",
    "generated": "resulted_in",
    "battled_in": "fought_in",
    "served_in": "participated_in",
    "engaged_in": "participated_in",
    "took_part_in": "participated_in",
}

STANDARD_RELATIONS: frozenset[str] = frozenset(
    {
        "founded",
        "invented",
        "discovered",
        "developed",
        "created",
        "led",
        "directed",
        "authored",
        "influenced",
        "inspired",
        "part_of",
        "uses",
        "requires",
        "caused",
        "resulted_in",
        "fought_in",
        "participated_in",
        "born_in",
        "died_in",
        "located_in",
        "related_to",
    }
)


_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "history": [
        "history",
        "war",
        "battle",
        "revolution",
        "empire",
        "dynasty",
        "political",
        "government",
        "military",
        "colonial",
        "medieval",
    ],
    "science": [
        "physics",
        "chemistry",
        "biology",
        "mathematics",
        "computer",
        "engineering",
        "technology",
        "algorithm",
        "quantum",
        "molecular",
    ],
    "biography": [
        "people",
        "person",
        "biography",
        "leader",
        "president",
        "scientist",
        "artist",
        "writer",
        "philosopher",
        "musician",
    ],
    "geography": [
        "country",
        "city",
        "region",
        "continent",
        "geography",
        "river",
        "mountain",
        "island",
        "ocean",
        "state",
    ],
}

_DOMAIN_PROMPTS: dict[str, str] = {
    "history": (
        "\n\nFocus especially on: causal relationships (what led to what), "
        "chronological sequences (before/after/during), key figures and their roles, "
        "alliances and conflicts between groups, and turning points."
    ),
    "science": (
        "\n\nFocus especially on: taxonomic/hierarchical relationships (X is a type of Y), "
        "inventions and discoveries (who invented/discovered what, when), "
        "dependencies (X requires/uses Y), and experimental findings."
    ),
    "biography": (
        "\n\nFocus especially on: life events (born, died, educated at), "
        "achievements and contributions, institutional affiliations, "
        "influences (who influenced whom), and notable works or creations."
    ),
    "geography": (
        "\n\nFocus especially on: spatial relationships (located in, borders, contains), "
        "demographic facts (population, language, government type), "
        "natural features, and economic/cultural significance."
    ),
}


def detect_domain(categories: list[str]) -> str | None:
    """Classify article domain from its categories.

    Returns one of: 'history', 'science', 'biography', 'geography', or None.
    """
    if not categories:
        return None
    combined = " ".join(c.lower() for c in categories)
    best_domain = None
    best_score = 0
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > best_score:
            best_score = score
            best_domain = domain
    return best_domain if best_score > 0 else None


def normalize_relation(relation: str) -> str:
    """Normalize a relation string to a standard canonical form.

    Lowercases, replaces spaces with underscores, and maps synonyms.
    Unknown relations are kept as-is.
    """
    normalized = relation.strip().lower().replace(" ", "_").replace("-", "_")
    if normalized in STANDARD_RELATIONS:
        return normalized
    return _RELATION_SYNONYMS.get(normalized, normalized)


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
        self,
        title: str,
        sections: list[dict],
        max_sections: int = 5,
        domain: str | None = None,
    ) -> ExtractionResult:
        """
        Extract entities and relationships from an article.

        Args:
            title: Article title
            sections: Parsed sections (from parser.py)
            max_sections: Limit sections to process (cost control)
            domain: Optional domain hint ('history', 'science', 'biography',
                'geography') for domain-tuned extraction. Use detect_domain()
                to auto-detect from article categories.

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

        # Append domain-specific prompt if available
        domain_suffix = _DOMAIN_PROMPTS.get(domain, "") if domain else ""
        if domain_suffix:
            prompt += domain_suffix

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
                    relation=normalize_relation(r.get("relation", "related_to")),
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
