"""Tests for SeedAgent and topics file parsing."""

import json
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# SeedAgent: prompt parsing
# ---------------------------------------------------------------------------
class TestSeedAgentPrompt:
    """Test Claude prompt construction and JSON parsing."""

    def _make_mock_response(self, text: str) -> MagicMock:
        mock = MagicMock()
        mock.content = [MagicMock()]
        mock.content[0].text = text
        return mock

    def test_parses_json_response(self):
        body = json.dumps(
            {
                "topic": "Quantum Computing",
                "category": "Physics & Computing",
                "articles": [
                    {"title": "Quantum computing"},
                    {"title": "Qubit"},
                    {"title": "Quantum entanglement"},
                ],
            }
        )
        with patch("wikigr.agent.seed_agent.Anthropic") as mock_cls:
            client = MagicMock()
            client.messages.create.return_value = self._make_mock_response(body)
            mock_cls.return_value = client

            from wikigr.agent.seed_agent import SeedAgent

            agent = SeedAgent()
            titles = agent._generate_titles_for_topic("Quantum Computing")

        assert len(titles) == 3
        assert titles[0]["title"] == "Quantum computing"
        assert titles[0]["category"] == "Physics & Computing"

    def test_handles_markdown_json_wrapper(self):
        body = '```json\n{"topic":"T","category":"C","articles":[{"title":"A"}]}\n```'
        with patch("wikigr.agent.seed_agent.Anthropic") as mock_cls:
            client = MagicMock()
            client.messages.create.return_value = self._make_mock_response(body)
            mock_cls.return_value = client

            from wikigr.agent.seed_agent import SeedAgent

            agent = SeedAgent()
            titles = agent._generate_titles_for_topic("T")

        assert len(titles) == 1
        assert titles[0]["title"] == "A"

    def test_returns_empty_on_invalid_json(self):
        with patch("wikigr.agent.seed_agent.Anthropic") as mock_cls:
            client = MagicMock()
            client.messages.create.return_value = self._make_mock_response("not json")
            mock_cls.return_value = client

            from wikigr.agent.seed_agent import SeedAgent

            agent = SeedAgent()
            titles = agent._generate_titles_for_topic("Bad")

        assert titles == []


# ---------------------------------------------------------------------------
# SeedAgent: Wikipedia validation
# ---------------------------------------------------------------------------
class TestSeedAgentValidation:
    """Test Wikipedia title validation and redirect handling."""

    def test_filters_missing_titles(self):
        mock_wiki = MagicMock()
        mock_wiki.validate_titles.return_value = {
            "Quantum computing": "Quantum computing",
            "Not Real": None,
            "Qubit": "Qubit",
        }

        with patch("wikigr.agent.seed_agent.Anthropic"):
            from wikigr.agent.seed_agent import SeedAgent

            agent = SeedAgent(wikipedia_client=mock_wiki)

        candidates = [
            {"title": "Quantum computing", "category": "Physics"},
            {"title": "Not Real", "category": "Physics"},
            {"title": "Qubit", "category": "Physics"},
        ]

        valid = agent._validate_titles(candidates)
        assert len(valid) == 2
        assert all(c["title"] != "Not Real" for c in valid)

    def test_replaces_redirects_with_canonical(self):
        mock_wiki = MagicMock()
        mock_wiki.validate_titles.return_value = {
            "AI": "Artificial intelligence",
        }

        with patch("wikigr.agent.seed_agent.Anthropic"):
            from wikigr.agent.seed_agent import SeedAgent

            agent = SeedAgent(wikipedia_client=mock_wiki)

        valid = agent._validate_titles([{"title": "AI", "category": "Tech"}])
        assert len(valid) == 1
        assert valid[0]["title"] == "Artificial intelligence"

    def test_empty_candidates(self):
        with patch("wikigr.agent.seed_agent.Anthropic"):
            from wikigr.agent.seed_agent import SeedAgent

            agent = SeedAgent()

        assert agent._validate_titles([]) == []


# ---------------------------------------------------------------------------
# SeedAgent: end-to-end flow (all mocked)
# ---------------------------------------------------------------------------
class TestSeedAgentE2E:
    """Test full generate_seeds pipeline with mocked Claude and Wikipedia."""

    def test_full_flow(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps(
            {
                "topic": "AI",
                "category": "Computer Science",
                "articles": [
                    {"title": "Machine learning"},
                    {"title": "Deep learning"},
                    {"title": "FakeArticle"},
                ],
            }
        )

        mock_wiki = MagicMock()
        mock_wiki.validate_titles.return_value = {
            "Machine learning": "Machine learning",
            "Deep learning": "Deep learning",
            "FakeArticle": None,
        }

        with patch("wikigr.agent.seed_agent.Anthropic") as mock_cls:
            client = MagicMock()
            client.messages.create.return_value = mock_response
            mock_cls.return_value = client

            from wikigr.agent.seed_agent import SeedAgent

            agent = SeedAgent(wikipedia_client=mock_wiki, seeds_per_topic=10)
            result = agent.generate_seeds(["AI"])

        assert "metadata" in result
        assert "seeds" in result
        assert result["metadata"]["total_seeds"] == 2
        assert len(result["seeds"]) == 2
        assert all(s["expansion_depth"] == 0 for s in result["seeds"])
        assert all(s["category"] == "Computer Science" for s in result["seeds"])

    def test_deduplicates_across_topics(self):
        """Same article suggested for two topics should appear only once in combined."""
        response_1 = MagicMock()
        response_1.content = [MagicMock()]
        response_1.content[0].text = json.dumps(
            {
                "topic": "AI",
                "category": "CS",
                "articles": [{"title": "Neural network"}],
            }
        )

        response_2 = MagicMock()
        response_2.content = [MagicMock()]
        response_2.content[0].text = json.dumps(
            {
                "topic": "Brain Science",
                "category": "Neuro",
                "articles": [{"title": "Neural network"}, {"title": "Neuroscience"}],
            }
        )

        mock_wiki = MagicMock()
        mock_wiki.validate_titles.return_value = {
            "Neural network": "Neural network",
            "Neuroscience": "Neuroscience",
        }

        with patch("wikigr.agent.seed_agent.Anthropic") as mock_cls:
            client = MagicMock()
            client.messages.create.side_effect = [response_1, response_2]
            mock_cls.return_value = client

            from wikigr.agent.seed_agent import SeedAgent

            agent = SeedAgent(wikipedia_client=mock_wiki, seeds_per_topic=5)
            result = agent.generate_seeds(["AI", "Brain Science"])

        titles = [s["title"] for s in result["seeds"]]
        assert titles.count("Neural network") == 1
        assert result["metadata"]["total_seeds"] == 2

    def test_generate_seeds_by_topic_returns_separate_dicts(self):
        """generate_seeds_by_topic returns one seed dict per topic."""
        response_1 = MagicMock()
        response_1.content = [MagicMock()]
        response_1.content[0].text = json.dumps(
            {
                "topic": "AI",
                "category": "CS",
                "articles": [{"title": "Machine learning"}],
            }
        )

        response_2 = MagicMock()
        response_2.content = [MagicMock()]
        response_2.content[0].text = json.dumps(
            {
                "topic": "Art",
                "category": "Arts",
                "articles": [{"title": "Painting"}, {"title": "Sculpture"}],
            }
        )

        mock_wiki = MagicMock()
        mock_wiki.validate_titles.side_effect = [
            {"Machine learning": "Machine learning"},
            {"Painting": "Painting", "Sculpture": "Sculpture"},
        ]

        with patch("wikigr.agent.seed_agent.Anthropic") as mock_cls:
            client = MagicMock()
            client.messages.create.side_effect = [response_1, response_2]
            mock_cls.return_value = client

            from wikigr.agent.seed_agent import SeedAgent

            agent = SeedAgent(wikipedia_client=mock_wiki, seeds_per_topic=5)
            result = agent.generate_seeds_by_topic(["AI", "Art"])

        assert "AI" in result
        assert "Art" in result
        assert result["AI"]["metadata"]["total_seeds"] == 1
        assert result["Art"]["metadata"]["total_seeds"] == 2
        assert result["AI"]["seeds"][0]["title"] == "Machine learning"


# ---------------------------------------------------------------------------
# Topics file parsing
# ---------------------------------------------------------------------------
class TestTopicsFileParsing:
    """Test parse_topics_file with various formats."""

    def test_plain_text(self, tmp_path):
        f = tmp_path / "topics.txt"
        f.write_text("Quantum Computing\nRenaissance Art\nMarine Biology\n")

        from wikigr.cli import parse_topics_file

        assert parse_topics_file(str(f)) == [
            "Quantum Computing",
            "Renaissance Art",
            "Marine Biology",
        ]

    def test_markdown_bullets(self, tmp_path):
        f = tmp_path / "topics.md"
        f.write_text("# My Topics\n\n- Quantum Computing\n- Renaissance Art\n* Marine Biology\n")

        from wikigr.cli import parse_topics_file

        assert parse_topics_file(str(f)) == [
            "Quantum Computing",
            "Renaissance Art",
            "Marine Biology",
        ]

    def test_numbered_list(self, tmp_path):
        f = tmp_path / "topics.md"
        f.write_text("1. Alpha\n2. Beta\n3. Gamma\n")

        from wikigr.cli import parse_topics_file

        assert parse_topics_file(str(f)) == ["Alpha", "Beta", "Gamma"]

    def test_ignores_blanks_and_headers(self, tmp_path):
        f = tmp_path / "topics.md"
        f.write_text("# Header\n\nQuantum Computing\n\n# Another\nArt\n")

        from wikigr.cli import parse_topics_file

        assert parse_topics_file(str(f)) == ["Quantum Computing", "Art"]

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("# Just a header\n\n")

        from wikigr.cli import parse_topics_file

        assert parse_topics_file(str(f)) == []


# ---------------------------------------------------------------------------
# Slugify helper
# ---------------------------------------------------------------------------
class TestSlugify:
    """Test the _slugify helper used for DB filenames."""

    def test_basic(self):
        from wikigr.cli import _slugify

        assert _slugify("Operating Systems") == "operating-systems"

    def test_special_chars(self):
        from wikigr.cli import _slugify

        assert _slugify("C++ & Rust!") == "c-rust"

    def test_extra_spaces(self):
        from wikigr.cli import _slugify

        assert _slugify("  Distributed  Systems  ") == "distributed-systems"
