"""RAG-augmented Cypher query generation using OpenCypher expert pack patterns.

Uses retrieved working Cypher examples as context to improve LLM Cypher generation.
Replaces blind LLM prompting with pattern-informed generation.
"""

import json
import logging
from typing import Any

from anthropic import Anthropic

logger = logging.getLogger(__name__)

CYPHER_RAG_PROMPT = """You are a Cypher query generator for a Kuzu graph database.

## TARGET SCHEMA

{schema}

## KUZU SYNTAX RULES (NOT Neo4j)

1. Parameters: $param (NOT {{param}} or {{{{param}}}})
2. Case-insensitive match: lower(x) CONTAINS lower($param)
3. Variable-length paths: [:REL*1..3] (MUST have upper bound)
4. No apoc.* functions -- they do not exist in Kuzu
5. No LENGTH() on strings -- use string_length() or avoid it
6. LIMIT must be a literal integer, not a parameter
7. String comparison: use CONTAINS, STARTS WITH, ENDS WITH (not LIKE or regex)
8. Return columns must use AS aliases
9. Always bind the user's search term to $q parameter

## WORKING CYPHER PATTERNS (from similar questions)

{patterns}

## TASK

Generate a Cypher query to answer: {question}

Choose the SIMPLEST pattern that answers the question. Prefer patterns from the examples above.

Return ONLY valid JSON:
{{"type": "<query_type>", "cypher": "<query>", "cypher_params": {{"q": "<search_term>"}}, "explanation": "<brief reason>"}}

The cypher_params MUST contain "q" bound to the key search term extracted from the question."""


def build_schema_string(conn: Any) -> str:
    """Extract schema from Kuzu database for prompt injection.

    Args:
        conn: Kuzu database connection

    Returns:
        Formatted schema string listing tables and their types,
        or "(schema unavailable)" on failure.
    """
    try:
        tables_df = conn.execute("CALL show_tables() RETURN *").get_as_df()
        parts = []
        for _, row in tables_df.iterrows():
            name = row.get("name", "")
            ttype = row.get("type", "")
            parts.append(f"- {name} ({ttype})")
        return "\n".join(parts) if parts else "(schema unavailable)"
    except Exception as e:
        logger.warning("Schema extraction failed: %s", e)
        return "(schema unavailable)"


class CypherRAG:
    """Generate Kuzu Cypher queries using retrieved OpenCypher patterns as context.

    Combines a pattern retrieval manager (e.g. FewShotManager) with Claude API
    to produce pattern-informed Cypher queries instead of blind generation.

    Args:
        pattern_manager: Object with find_similar_examples(query, k) method.
        claude_client: Anthropic client instance.
        schema: Database schema string for prompt context.
        model: Claude model name for generation.
    """

    def __init__(
        self,
        pattern_manager: Any,
        claude_client: Anthropic,
        schema: str,
        model: str = "claude-opus-4-6",
    ):
        self.patterns = pattern_manager
        self.claude = claude_client
        self.schema = schema
        self.model = model

    def generate_cypher(self, question: str, k_patterns: int = 3, max_tokens: int = 512) -> dict:
        """Generate a Cypher query plan informed by retrieved patterns.

        Args:
            question: Natural language question to convert to Cypher.
            k_patterns: Number of similar patterns to retrieve.
            max_tokens: Max tokens for Claude response.

        Returns:
            Dict with keys: type, cypher, cypher_params, explanation, patterns_used.
        """
        # Retrieve relevant patterns
        try:
            examples = self.patterns.find_similar_examples(question, k=k_patterns)
        except Exception as e:
            logger.debug("Pattern retrieval failed: %s", e)
            examples = []

        # Format patterns for prompt
        pattern_text = self._format_patterns(examples)

        # Build prompt
        prompt = CYPHER_RAG_PROMPT.format(
            schema=self.schema,
            patterns=pattern_text,
            question=question,
        )

        # Call Claude
        try:
            response = self.claude.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            if not response.content:
                return self._safe_fallback(question)

            text = response.content[0].text.strip()
            # Parse JSON from response (strip markdown fences if present)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(text)

            # Ensure cypher_params always has "q"
            if "cypher_params" not in parsed:
                parsed["cypher_params"] = {"q": question}
            elif "q" not in parsed["cypher_params"]:
                parsed["cypher_params"]["q"] = question

            parsed["patterns_used"] = len(examples)
            return parsed

        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("CypherRAG parse error: %s", e)
            return self._safe_fallback(question)
        except Exception as e:
            logger.warning("CypherRAG API error: %s", e)
            return self._safe_fallback(question)

    def _format_patterns(self, examples: list[dict]) -> str:
        """Format retrieved examples into prompt-ready pattern text.

        Args:
            examples: List of dicts from pattern_manager.find_similar_examples().

        Returns:
            Formatted string of numbered patterns, or placeholder if none.
        """
        if not examples:
            return "(no relevant patterns found)"
        parts = []
        for i, ex in enumerate(examples, 1):
            q = ex.get("question", ex.get("query", ""))
            a = ex.get("answer", ex.get("ground_truth", ""))
            parts.append(f"### Pattern {i}\nQuestion: {q}\nCypher: {a}")
        return "\n\n".join(parts)

    @staticmethod
    def _safe_fallback(question: str) -> dict:
        """Return a safe entity-search fallback when generation fails.

        Extracts meaningful search terms from the question, filtering
        out common stop words.

        Args:
            question: Original natural language question.

        Returns:
            Dict with a simple title-search Cypher plan.
        """
        stop_words = {
            "what",
            "which",
            "where",
            "when",
            "does",
            "about",
            "between",
            "from",
            "that",
            "this",
            "with",
            "have",
            "their",
        }
        words = question.split()
        search_term = (
            " ".join(w for w in words if len(w) > 3 and w.lower() not in stop_words)[:50]
            or question[:50]
        )
        return {
            "type": "entity_search",
            "cypher": "MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($q) RETURN a.title AS title LIMIT 10",
            "cypher_params": {"q": search_term},
            "explanation": "Safe fallback: simple title search",
            "patterns_used": 0,
        }
