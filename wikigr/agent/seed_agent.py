"""
Seed generation agent for WikiGR.

Uses Claude to generate Wikipedia seed articles from user-provided topics,
validates them against the Wikipedia API, and produces seed data compatible
with the expansion pipeline.
"""

import json
import logging
from datetime import datetime, timezone

from anthropic import Anthropic

from bootstrap.src.wikipedia.api_client import WikipediaAPIClient

logger = logging.getLogger(__name__)


class SeedAgent:
    """Generates Wikipedia seed articles from topic descriptions using Claude.

    Takes a list of topic strings, asks Claude to suggest real Wikipedia
    article titles for each, validates them against the Wikipedia API,
    and returns seed data in the canonical format consumed by
    RyuGraphOrchestrator.initialize_seeds().

    Args:
        anthropic_api_key: API key (or uses ANTHROPIC_API_KEY env var)
        model: Claude model for seed generation
        seeds_per_topic: Target number of validated seeds per topic
        wikipedia_client: Optional pre-configured Wikipedia client

    Example:
        >>> agent = SeedAgent()
        >>> seeds = agent.generate_seeds(["Quantum Computing", "Marine Biology"])
        >>> print(seeds["metadata"]["total_seeds"])
        >>> print(seeds["seeds"][0]["title"])
    """

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        model: str = "claude-opus-4-6",
        seeds_per_topic: int = 10,
        wikipedia_client: WikipediaAPIClient | None = None,
    ):
        self.claude = Anthropic(api_key=anthropic_api_key)
        self.model = model
        self.seeds_per_topic = seeds_per_topic
        self.wiki_client = wikipedia_client or WikipediaAPIClient()

    def generate_seeds(self, topics: list[str]) -> dict:
        """Generate validated seed data from a list of topics (combined).

        All topics are merged into a single seed set with deduplication.

        Args:
            topics: List of topic strings (e.g. ["Quantum Computing", "Renaissance Art"])

        Returns:
            Seed data dict with "metadata" and "seeds" keys, compatible with
            the format in bootstrap/data/seeds_1k.json.
        """
        per_topic = self.generate_seeds_by_topic(topics)

        # Merge all topics into one seed set, deduplicating
        seen: set[str] = set()
        all_seeds: list[dict] = []
        for seed_data in per_topic.values():
            for s in seed_data["seeds"]:
                if s["title"].lower() not in seen:
                    seen.add(s["title"].lower())
                    all_seeds.append(s)

        categories = list({s["category"] for s in all_seeds})
        return {
            "metadata": {
                "total_seeds": len(all_seeds),
                "categories": len(categories),
                "topics": topics,
                "purpose": f"Generated from {len(topics)} topics",
                "created_date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            },
            "seeds": all_seeds,
        }

    def generate_seeds_by_topic(self, topics: list[str]) -> dict[str, dict]:
        """Generate validated seed data for each topic separately.

        Args:
            topics: List of topic strings

        Returns:
            Dict mapping each topic string to its own seed data dict.
        """
        result: dict[str, dict] = {}

        for topic in topics:
            logger.info(f"Generating seed candidates for topic: {topic}")
            candidates = self._generate_titles_for_topic(topic)
            logger.info(f"  Claude suggested {len(candidates)} candidates")

            # Deduplicate within topic
            seen: set[str] = set()
            unique: list[dict] = []
            for c in candidates:
                if c["title"].lower() not in seen:
                    seen.add(c["title"].lower())
                    unique.append(c)

            validated = self._validate_titles(unique)
            logger.info(f"  Validated: {len(validated)}/{len(unique)}")

            categories = list({s["category"] for s in validated})
            result[topic] = {
                "metadata": {
                    "total_seeds": len(validated),
                    "categories": len(categories),
                    "topics": [topic],
                    "purpose": f"Generated for topic: {topic}",
                    "created_date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
                },
                "seeds": [
                    {
                        "title": s["title"],
                        "category": s["category"],
                        "expansion_depth": 0,
                    }
                    for s in validated
                ],
            }

        return result

    def _generate_titles_for_topic(self, topic: str) -> list[dict]:
        """Use Claude to generate candidate Wikipedia article titles for one topic.

        Requests more titles than needed (seeds_per_topic + 5) to account
        for validation failures.

        Returns:
            List of {"title": str, "category": str} dicts.
        """
        request_count = self.seeds_per_topic + 5

        prompt = f"""You are a Wikipedia expert. Generate exactly {request_count} real Wikipedia article titles that are excellent starting points for building a knowledge graph about: "{topic}"

Requirements:
1. Each title MUST be an exact, existing Wikipedia article title (case-sensitive, including parenthetical disambiguation like "Python (programming language)")
2. Choose diverse articles: foundational concepts, key people, important events, and applications
3. Prefer broad, well-developed articles over stubs
4. Do NOT include disambiguation pages, "List of..." pages, or redirect targets

Return ONLY valid JSON:
{{
  "topic": "{topic}",
  "category": "A short category label for this topic",
  "articles": [
    {{"title": "Exact Wikipedia Article Title"}},
    {{"title": "Another Article Title"}}
  ]
}}"""

        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            # Re-raise auth errors — they won't resolve by retrying
            try:
                from anthropic import AuthenticationError

                if isinstance(e, AuthenticationError):
                    raise ValueError(
                        "Anthropic API authentication failed. "
                        "Set ANTHROPIC_API_KEY or pass anthropic_api_key=."
                    ) from e
            except ImportError as imp_err:
                logger.debug("Optional import unavailable: %s", imp_err)
            logger.error(f"Failed to generate titles for '{topic}': {type(e).__name__}: {e}")
            return []

        if not response.content:
            logger.warning(f"Empty response from Claude for topic '{topic}'")
            return []

        content = response.content[0].text

        try:
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            category = data.get("category", topic)

            return [{"title": a["title"], "category": category} for a in data.get("articles", [])]

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse titles for '{topic}': {e}")
            return []

    def _validate_titles(self, candidates: list[dict]) -> list[dict]:
        """Validate candidate titles against Wikipedia and return only valid ones.

        Replaces titles with their canonical form (following redirects).
        """
        if not candidates:
            return []

        titles = [c["title"] for c in candidates]
        validation = self.wiki_client.validate_titles(titles)

        validated: list[dict] = []
        for candidate in candidates:
            canonical = validation.get(candidate["title"])
            if canonical is not None:
                validated.append(
                    {
                        "title": canonical,
                        "category": candidate["category"],
                    }
                )
            else:
                logger.warning(f"  Dropped invalid title: {candidate['title']}")

        return validated
