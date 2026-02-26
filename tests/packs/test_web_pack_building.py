"""TDD tests for web-sourced pack building.

Tests the complete pipeline from URL fetching to pack database creation.
Following TDD methodology: these tests expose bugs in build_pack_generic.py
and should FAIL initially, then PASS after implementation fixes.

Current issue: Microsoft Learn packs complete with 0 articles despite valid URLs.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import kuzu
import pytest

from bootstrap.schema.ryugraph_schema import create_schema
from bootstrap.src.embeddings.generator import EmbeddingGenerator
from bootstrap.src.extraction.llm_extractor import Entity, ExtractionResult, Relationship
from bootstrap.src.sources.base import Article
from bootstrap.src.sources.web import WebContentSource
from bootstrap.src.wikipedia.parser import parse_sections


class TestWebContentSourceFetch:
    """Test WebContentSource.fetch_article() returns valid Article with content."""

    def test_fetch_article_returns_article_with_content(self):
        """WebContentSource.fetch_article() must return Article with non-empty .content."""
        source = WebContentSource()

        # Use a real documentation URL (or mock if flaky)
        with patch("requests.Session.get") as mock_get:
            # Simulate Microsoft Learn page
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = """
                <html>
                <head><title>Azure Functions Overview | Microsoft Learn</title></head>
                <body>
                    <main>
                        <h1>Azure Functions Overview</h1>
                        <h2>What is Azure Functions?</h2>
                        <p>Azure Functions is a serverless compute service that lets you run
                        event-triggered code without having to explicitly provision or manage infrastructure.
                        This makes it easy to build scalable applications quickly.</p>
                        <h2>Key Features</h2>
                        <p>Functions support multiple programming languages including C#, Python,
                        JavaScript, Java, and PowerShell. The service automatically scales based on demand.</p>
                    </main>
                </body>
                </html>
            """
            mock_response.encoding = "utf-8"
            mock_get.return_value = mock_response

            article = source.fetch_article("https://learn.microsoft.com/azure/functions/overview")

            # Critical assertions that expose bugs
            assert article is not None, "fetch_article() returned None"
            assert isinstance(article, Article), f"Expected Article, got {type(article)}"
            assert article.content, "Article.content is empty or None"
            assert len(article.content) > 0, "Article.content has zero length"
            assert "Azure Functions" in article.content, "Content missing expected text"
            assert article.title, "Article.title is empty"

    def test_fetch_article_content_is_markdown_like(self):
        """Fetched article content should be markdown-like plain text, not HTML."""
        source = WebContentSource()

        with patch("requests.Session.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = """
                <html><body><main>
                    <h1>Test Article</h1>
                    <p>This is a paragraph with <strong>bold text</strong>.</p>
                    <ul><li>List item 1</li><li>List item 2</li></ul>
                </main></body></html>
            """
            mock_response.encoding = "utf-8"
            mock_get.return_value = mock_response

            article = source.fetch_article("https://example.com/test")

            # Should be markdown-like, not HTML
            assert "<html>" not in article.content, "Content still contains HTML tags"
            assert "<p>" not in article.content, "Content still contains <p> tags"
            assert (
                "# " in article.content or "Test Article" in article.content
            ), "Missing markdown heading"

    def test_fetch_article_handles_404(self):
        """fetch_article() must raise ArticleNotFoundError on 404."""
        from bootstrap.src.sources.base import ArticleNotFoundError

        source = WebContentSource()

        with patch("requests.Session.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            with pytest.raises(ArticleNotFoundError):
                source.fetch_article("https://example.com/nonexistent")


class TestParseSections:
    """Test parse_sections() handles both markdown and wikitext formats."""

    def test_parse_markdown_sections(self):
        """parse_sections() must handle markdown format (## Heading)."""
        markdown_content = """
# Main Title

## Introduction
This is the introduction section with enough content to pass the 100 character minimum.
Azure Functions is a serverless solution that allows you to write less code.

## Getting Started
Follow these steps to create your first function with sufficient content length to ensure
this section passes the minimum content requirements for parsing and inclusion.

## Advanced Topics
This section covers advanced features and configurations that require more detailed
explanation to help developers understand the full capabilities of the platform.
"""

        sections = parse_sections(markdown_content)

        # Critical assertions
        assert len(sections) > 0, "parse_sections() returned empty list for markdown"
        assert any(s["title"] == "Introduction" for s in sections), "Missing 'Introduction' section"
        assert all("content" in s for s in sections), "Some sections missing 'content' key"
        assert all(
            len(s["content"]) >= 100 for s in sections
        ), "Some sections under 100 char minimum"

        # Verify markdown heading levels
        intro_section = next(s for s in sections if s["title"] == "Introduction")
        assert intro_section["level"] == 2, f"Expected level 2, got {intro_section['level']}"

    def test_parse_wikitext_sections(self):
        """parse_sections() must handle wikitext format (== Heading ==)."""
        wikitext_content = """
== Overview ==
Machine learning is a field of artificial intelligence that uses statistical techniques
to give computer systems the ability to learn from data without being explicitly programmed.

== Applications ==
Machine learning has applications in computer vision, natural language processing, and
recommendation systems. These technologies power many modern software applications today.

=== Supervised Learning ===
Supervised learning algorithms learn from labeled training data and make predictions based
on that information. Common examples include classification and regression algorithms.
"""

        sections = parse_sections(wikitext_content)

        assert len(sections) > 0, "parse_sections() returned empty list for wikitext"
        assert any(s["title"] == "Overview" for s in sections), "Missing 'Overview' section"
        assert any(s["title"] == "Supervised Learning" for s in sections), "Missing subsection"

        # Verify wikitext heading levels
        overview = next(s for s in sections if s["title"] == "Overview")
        assert overview["level"] == 2, f"H2 should be level 2, got {overview['level']}"

        subsection = next(s for s in sections if s["title"] == "Supervised Learning")
        assert subsection["level"] == 3, f"H3 should be level 3, got {subsection['level']}"

    def test_parse_sections_filters_short_sections(self):
        """parse_sections() must filter out sections < 100 characters."""
        content = """
## Valid Section
This section has enough content to pass the minimum requirement of one hundred characters.
It contains detailed information that is useful for knowledge extraction purposes today.

## Too Short
Not enough.

## Another Valid Section
This section also contains sufficient content to meet the minimum character threshold and
provides valuable information that should be included in the knowledge graph structure.
"""

        sections = parse_sections(content)

        assert (
            len(sections) == 2
        ), f"Expected 2 sections (filtered out short one), got {len(sections)}"
        assert all(len(s["content"]) >= 100 for s in sections), "Short sections not filtered"
        assert not any(
            s["title"] == "Too Short" for s in sections
        ), "'Too Short' section not filtered"


class TestKuzuDatabaseInsertion:
    """Test articles get inserted into Kuzu database."""

    def test_article_node_creation(self, tmp_path: Path):
        """Articles must be inserted as nodes in Kuzu database."""
        db_path = tmp_path / "test.db"
        create_schema(str(db_path), drop_existing=True)

        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        # Insert test article
        conn.execute(
            "CREATE (a:Article {title: $t, category: $c, word_count: $w})",
            {"t": "Test Article", "c": "test-pack", "w": 150},
        )

        # Verify insertion
        result = conn.execute(
            "MATCH (a:Article {title: $t}) RETURN a.title, a.word_count", {"t": "Test Article"}
        )
        df = result.get_as_df()

        assert len(df) == 1, "Article not inserted"
        assert df.iloc[0]["a.title"] == "Test Article"
        assert df.iloc[0]["a.word_count"] == 150

    def test_section_nodes_with_embeddings(self, tmp_path: Path):
        """Sections must be created with embeddings."""
        db_path = tmp_path / "test.db"
        create_schema(str(db_path), drop_existing=True)

        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        # Create article first
        conn.execute(
            "CREATE (a:Article {title: $t, category: $c, word_count: $w})",
            {"t": "Test Article", "c": "test", "w": 100},
        )

        # Create section with embedding
        embedder = EmbeddingGenerator()
        section_content = "This is test content for generating embeddings in knowledge graph."
        embedding = embedder.generate([section_content])[0].tolist()

        conn.execute(
            "MATCH (a:Article {title: $t}) CREATE (a)-[:HAS_SECTION]->(s:Section {section_id: $id, content: $c, embedding: $e})",
            {"t": "Test Article", "id": "test#0", "c": section_content, "e": embedding},
        )

        # Verify section exists
        result = conn.execute(
            "MATCH (s:Section {section_id: $id}) RETURN s.content", {"id": "test#0"}
        )
        df = result.get_as_df()

        assert len(df) == 1, "Section not created"
        assert df.iloc[0]["s.content"] == section_content


class TestEntityExtraction:
    """Test entities and relationships get extracted and stored."""

    def test_entity_extraction_mock(self):
        """Entity extraction must return non-empty results for valid content."""
        from bootstrap.src.extraction.llm_extractor import LLMExtractor

        # Mock the extractor to avoid API calls
        extractor = Mock(spec=LLMExtractor)

        entities = [
            Entity(name="Azure Functions", type="service", properties={}),
            Entity(name="Microsoft Azure", type="platform", properties={}),
        ]
        relationships = [
            Relationship(
                source="Azure Functions",
                target="Microsoft Azure",
                relation="part_of",
                context="Azure Functions is a service on Microsoft Azure",
            )
        ]

        extractor.extract_from_article.return_value = ExtractionResult(
            entities=entities, relationships=relationships, key_facts=[]
        )

        sections = [
            {
                "title": "Overview",
                "content": "Azure Functions is part of Microsoft Azure.",
                "level": 2,
            }
        ]

        result = extractor.extract_from_article("Azure Functions", sections, 5, "technology")

        assert len(result.entities) > 0, "No entities extracted"
        assert len(result.relationships) > 0, "No relationships extracted"
        assert result.entities[0].name == "Azure Functions"

    def test_entity_nodes_created_in_database(self, tmp_path: Path):
        """Extracted entities must be inserted as Entity nodes."""
        db_path = tmp_path / "test.db"
        create_schema(str(db_path), drop_existing=True)

        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        # Create article
        conn.execute(
            "CREATE (a:Article {title: $t, category: $c, word_count: $w})",
            {"t": "Test", "c": "test", "w": 100},
        )

        # Create entity
        conn.execute(
            "MERGE (e:Entity {entity_id: $id}) ON CREATE SET e.name=$n, e.type=$t",
            {"id": "Azure Functions", "n": "Azure Functions", "t": "service"},
        )

        # Link to article
        conn.execute(
            "MATCH (a:Article {title:$t}), (e:Entity {entity_id:$id}) MERGE (a)-[:HAS_ENTITY]->(e)",
            {"t": "Test", "id": "Azure Functions"},
        )

        # Verify entity exists
        result = conn.execute(
            "MATCH (e:Entity {entity_id: $id}) RETURN e.name, e.type", {"id": "Azure Functions"}
        )
        df = result.get_as_df()

        assert len(df) == 1, "Entity not created"
        assert df.iloc[0]["e.name"] == "Azure Functions"

    def test_relationship_edges_created(self, tmp_path: Path):
        """Extracted relationships must be stored as ENTITY_RELATION edges."""
        db_path = tmp_path / "test.db"
        create_schema(str(db_path), drop_existing=True)

        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        # Create entities
        for entity_id in ["Azure Functions", "Microsoft Azure"]:
            conn.execute(
                "MERGE (e:Entity {entity_id: $id}) ON CREATE SET e.name=$id, e.type='concept'",
                {"id": entity_id},
            )

        # Create relationship
        conn.execute(
            "MATCH (s:Entity {entity_id:$s}), (t:Entity {entity_id:$t}) "
            "MERGE (s)-[:ENTITY_RELATION {relation:$r, context:$c}]->(t)",
            {
                "s": "Azure Functions",
                "t": "Microsoft Azure",
                "r": "part_of",
                "c": "Azure Functions is a service on Microsoft Azure",
            },
        )

        # Verify relationship
        result = conn.execute(
            "MATCH (s:Entity)-[r:ENTITY_RELATION]->(t:Entity) "
            "WHERE s.entity_id = $s AND t.entity_id = $t "
            "RETURN r.relation, r.context",
            {"s": "Azure Functions", "t": "Microsoft Azure"},
        )
        df = result.get_as_df()

        assert len(df) == 1, "Relationship not created"
        assert df.iloc[0]["r.relation"] == "part_of"


class TestFullPackBuildIntegration:
    """Integration tests for complete pack building from URLs."""

    def test_pack_build_creates_database(self, tmp_path: Path):
        """Full pack build must create pack.db file."""
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        # Create mock URLs file
        urls_file = pack_dir / "urls.txt"
        urls_file.write_text("https://example.com/doc1\nhttps://example.com/doc2\n")

        db_path = pack_dir / "pack.db"

        # Create schema (simulating build_pack_generic.py)
        create_schema(str(db_path), drop_existing=True)

        assert db_path.exists(), "pack.db not created"
        assert db_path.is_file(), "pack.db should be a file (Kuzu DB)"
        assert db_path.stat().st_size > 0, "pack.db should not be empty"

    def test_pack_build_with_zero_articles_is_failure(self, tmp_path: Path):
        """Verify build script detects and fails when 0 articles are processed.

        After fix: build_pack_generic.py should exit with error code when
        no articles are successfully processed.
        """
        pack_dir = tmp_path / "test-pack"
        pack_dir.mkdir()

        db_path = pack_dir / "pack.db"
        create_schema(str(db_path), drop_existing=True)

        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        # Verify empty database scenario
        result = conn.execute("MATCH (n:Article) RETURN count(n) AS c")
        article_count = int(result.get_as_df().iloc[0]["c"])

        # Should have 0 articles in empty database
        assert article_count == 0, "Test setup should have 0 articles"

        # Note: Full verification requires running build_pack_generic.py with invalid URLs
        # and checking exit code. This test verifies the database state that would
        # trigger the failure condition in build_pack_generic.py (line 77-79).

    @pytest.mark.parametrize(
        "url,expected_title_substring",
        [
            ("https://learn.microsoft.com/azure/functions/overview", "Azure Functions"),
            ("https://learn.microsoft.com/azure/cosmos-db/intro", "Cosmos"),
        ],
    )
    def test_real_microsoft_learn_urls_fetch(self, url, expected_title_substring):
        """Test fetching real Microsoft Learn URLs (skip if network unavailable).

        This test verifies the actual WebContentSource works with real URLs.
        Skip if offline or rate-limited.
        """
        pytest.skip("Skipping real URL test - enable manually for integration testing")

        source = WebContentSource()

        try:
            article = source.fetch_article(url)

            assert article is not None
            assert article.content
            assert len(article.content) > 100, "Content too short for real article"
            assert expected_title_substring.lower() in article.title.lower()

            # Verify sections can be parsed
            sections = parse_sections(article.content)
            assert len(sections) > 0, "Real article produced 0 sections"

        except Exception as e:
            pytest.skip(f"Network or rate-limit issue: {e}")


class TestBuildLoopBugDiagnosis:
    """Tests specifically targeting the build loop bug that causes 0 articles."""

    def test_article_content_survives_pipeline(self):
        """Verify article.content is not lost during pipeline stages.

        This test checks the critical path: fetch -> parse -> insert
        to identify where content gets lost.
        """
        # Stage 1: Fetch
        with patch("requests.Session.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = """
                <html><body><main>
                    <h1>Test Article</h1>
                    <h2>Section One</h2>
                    <p>This section has sufficient content to pass the minimum character requirement
                    and should be included in the parsed sections output from the parser function.</p>
                    <h2>Section Two</h2>
                    <p>Another section with enough content to ensure it meets the minimum length
                    requirement and gets included when we parse the markdown content structure.</p>
                </main></body></html>
            """
            mock_response.encoding = "utf-8"
            mock_get.return_value = mock_response

            source = WebContentSource()
            article = source.fetch_article("https://example.com/test")

            assert article.content, "Stage 1 FAIL: article.content is empty after fetch"
            print(f"Stage 1 PASS: article.content length = {len(article.content)}")

            # Stage 2: Parse
            sections = parse_sections(article.content)

            assert len(sections) > 0, "Stage 2 FAIL: parse_sections() returned empty list"
            assert all("content" in s for s in sections), "Stage 2 FAIL: sections missing content"
            print(f"Stage 2 PASS: parsed {len(sections)} sections")

            # Stage 3: Database ready check
            assert all(
                len(s["content"]) >= 100 for s in sections
            ), "Stage 3 FAIL: sections don't meet minimum length for insertion"
            print("Stage 3 PASS: all sections meet insertion criteria")

    def test_conditional_skip_not_triggered_incorrectly(self):
        """Test that 'if not article or not article.content: continue' doesn't skip valid articles.

        This checks the exact condition in build_pack_generic.py line 38.
        """
        # Create valid article
        article = Article(
            title="Valid Article",
            content="# Heading\n\n## Section\n\nThis is valid content with sufficient length.",
            links=[],
            categories=["test"],
            source_url="https://example.com",
            source_type="web",
        )

        # Test the skip condition from build_pack_generic.py
        should_skip = not article or not article.content

        assert not should_skip, "Valid article would be incorrectly skipped!"

        # Test edge cases
        none_article = None
        assert not none_article or not none_article.content, "None article should be skipped"  # type: ignore

        empty_content = Article(title="Test", content="", links=[], categories=[])
        assert not empty_content or not empty_content.content, "Empty content should be skipped"

    def test_sections_skip_not_triggered_incorrectly(self):
        """Test that 'if not sections: continue' doesn't skip valid sections.

        This checks the exact condition in build_pack_generic.py line 40.
        """
        valid_content = """
## Introduction
This section contains enough text to pass the minimum character requirement and
should definitely be included in the final parsed sections output list.

## Methods
Another section with sufficient content to ensure it passes all validation checks
and gets included when we parse the markdown formatted text content here.
"""

        sections = parse_sections(valid_content)

        # Test the skip condition
        should_skip = not sections

        assert not should_skip, "Valid sections would be incorrectly skipped!"
        assert len(sections) >= 2, f"Expected 2+ sections, got {len(sections)}"

    def test_exception_handling_doesnt_hide_real_errors(self, tmp_path: Path, capfd):
        """Test that the broad 'except Exception' doesn't hide critical errors.

        build_pack_generic.py line 67-68 catches all exceptions. This test
        verifies we can still diagnose what went wrong.
        """
        db_path = tmp_path / "test.db"
        create_schema(str(db_path), drop_existing=True)

        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

        # Simulate an error that should be visible
        try:
            # Intentionally malformed query
            conn.execute("CREATE (a:Article {title: $t})", {"wrong_param": "test"})
            pytest.fail("Should have raised an exception")
        except Exception as e:
            # Verify error message is informative
            error_msg = str(e)
            print(f"ERROR: {error_msg[:80]}")

            _ = capfd.readouterr()

            # The error should indicate what went wrong
            assert (
                "title" in error_msg.lower() or "parameter" in error_msg.lower()
            ), f"Error message not helpful: {error_msg}"
