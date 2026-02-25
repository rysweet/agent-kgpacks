"""Baseline evaluators for two-way comparison.

This module provides evaluators for:
1. Training baseline: Claude without any tools (training data only)
2. Knowledge pack baseline: Claude with knowledge pack retrieval
"""

import json
import time
from pathlib import Path

from anthropic import Anthropic

from wikigr.packs.eval.models import Answer, Question


class TrainingBaselineEvaluator:
    """Evaluate using Claude without any tools (training data only).

    This represents the baseline of what Claude knows from its training data,
    without access to any external information sources.
    """

    def __init__(self, api_key: str | None = None):
        """Initialize training baseline evaluator.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"

    def evaluate(self, questions: list[Question]) -> list[Answer]:
        """Evaluate questions using only training data.

        Args:
            questions: List of questions to answer

        Returns:
            List of answers with timing and cost information
        """
        answers = []

        for question in questions:
            start_time = time.time()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": question.question}],
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extract answer text
            answer_text = response.content[0].text if response.content else ""

            # Estimate cost (Sonnet 3.5: $3/MTok input, $15/MTok output)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = (input_tokens * 3 + output_tokens * 15) / 1_000_000

            answers.append(
                Answer(
                    question_id=question.id,
                    answer=answer_text,
                    source="training",
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                )
            )

        return answers


class KnowledgePackEvaluator:
    """Evaluate using Claude with knowledge pack retrieval.

    This represents the knowledge pack approach, where Claude uses a curated
    domain-specific knowledge graph for answering questions.
    """

    def __init__(self, pack_path: Path, api_key: str | None = None):
        """Initialize knowledge pack evaluator.

        Args:
            pack_path: Path to knowledge pack directory
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self.pack_path = pack_path
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"

    def _retrieve_context(self, question: str) -> str:
        """Retrieve relevant context from knowledge pack.

        Args:
            question: Question to find context for

        Returns:
            Retrieved context text
        """
        # Try real KG retrieval first
        try:
            from wikigr.packs.eval.kg_adapter import retrieve_from_pack

            return retrieve_from_pack(question, self.pack_path)
        except FileNotFoundError as e:
            # Fallback if pack.db doesn't exist (for tests without real DB)
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"KG retrieval failed: {e}")
            manifest_path = self.pack_path / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest = json.load(f)
                    return f"Knowledge pack: {manifest.get('description', 'No description')}"
            return "Knowledge graph unavailable. Please check configuration."
        except ValueError as e:
            # Question validation error
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Question validation failed: {e}")
            return "Invalid question provided."
        except Exception as e:
            # Log error with full details, return generic message
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"KG retrieval failed: {e}", exc_info=True)
            return "An error occurred while retrieving context. Please try again later."

    def evaluate(self, questions: list[Question]) -> list[Answer]:
        """Evaluate questions using knowledge pack retrieval.

        Args:
            questions: List of questions to answer

        Returns:
            List of answers with timing and cost information
        """
        answers = []

        for question in questions:
            start_time = time.time()

            # Retrieve relevant context
            context = self._retrieve_context(question.question)

            # Query Claude with context
            prompt = f"""You have access to a curated knowledge pack. Answer this question
using the provided context. Include citations.

Context:
{context}

Question: {question.question}

Provide a comprehensive answer with references to the context."""

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            latency_ms = (time.time() - start_time) * 1000

            answer_text = response.content[0].text if response.content else ""

            # Estimate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost_usd = (input_tokens * 3 + output_tokens * 15) / 1_000_000

            answers.append(
                Answer(
                    question_id=question.id,
                    answer=answer_text,
                    source="knowledge_pack",
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                )
            )

        return answers
