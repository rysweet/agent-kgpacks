"""
Tests for link discovery module
"""

import kuzu
import pytest

from ..link_discovery import LinkDiscovery


@pytest.fixture
def test_db_path(tmp_path):
    """Create temporary test database"""
    db_path = tmp_path / "test_link_discovery.db"
    yield str(db_path)
    # Cleanup handled by tmp_path


@pytest.fixture
def test_connection(test_db_path):
    """Create test database with schema"""
    db = kuzu.Database(test_db_path)
    conn = kuzu.Connection(db)

    # Create schema
    conn.execute("""
        CREATE NODE TABLE Article(
            title STRING,
            category STRING,
            word_count INT32,
            expansion_state STRING,
            expansion_depth INT32,
            claimed_at TIMESTAMP,
            processed_at TIMESTAMP,
            retry_count INT32,
            PRIMARY KEY(title)
        )
    """)

    conn.execute("""
        CREATE REL TABLE LINKS_TO(
            FROM Article TO Article,
            link_type STRING
        )
    """)

    yield conn


@pytest.fixture
def discovery(test_connection):
    """Create LinkDiscovery instance"""
    return LinkDiscovery(test_connection)


@pytest.fixture
def seed_article(test_connection):
    """Insert a seed article for testing"""
    test_connection.execute("""
        CREATE (a:Article {
            title: 'Python (programming language)',
            category: 'Computer Science',
            word_count: 5000,
            expansion_state: 'loaded',
            expansion_depth: 0,
            claimed_at: NULL,
            processed_at: timestamp('2026-02-08T00:00:00'),
            retry_count: 0
        })
    """)
    return "Python (programming language)"


class TestValidLinkFiltering:
    """Tests for _is_valid_link method"""

    def test_valid_simple_title(self, discovery):
        """Test simple valid article title"""
        assert discovery._is_valid_link("Python")
        assert discovery._is_valid_link("Machine Learning")
        assert discovery._is_valid_link("Artificial Intelligence")

    def test_valid_title_with_parentheses(self, discovery):
        """Test valid title with clarifying parentheses"""
        assert discovery._is_valid_link("Python (programming language)")
        assert discovery._is_valid_link("Mercury (planet)")

    def test_invalid_wikipedia_namespace(self, discovery):
        """Test filtering Wikipedia namespace pages"""
        assert not discovery._is_valid_link("Wikipedia:About")
        assert not discovery._is_valid_link("Wikipedia:Policies")

    def test_invalid_help_namespace(self, discovery):
        """Test filtering Help pages"""
        assert not discovery._is_valid_link("Help:Contents")
        assert not discovery._is_valid_link("Help:Editing")

    def test_invalid_template_namespace(self, discovery):
        """Test filtering Template pages"""
        assert not discovery._is_valid_link("Template:Infobox")
        assert not discovery._is_valid_link("Template:Citation needed")

    def test_invalid_file_namespace(self, discovery):
        """Test filtering File and Image pages"""
        assert not discovery._is_valid_link("File:Python_logo.svg")
        assert not discovery._is_valid_link("Image:Example.jpg")

    def test_invalid_category_namespace(self, discovery):
        """Test filtering Category pages"""
        assert not discovery._is_valid_link("Category:Programming languages")
        assert not discovery._is_valid_link("Category:Computer Science")

    def test_invalid_list_pages(self, discovery):
        """Test filtering 'List of' pages"""
        assert not discovery._is_valid_link("List of programming languages")
        assert not discovery._is_valid_link("List of countries")

    def test_invalid_disambiguation_pages(self, discovery):
        """Test filtering disambiguation pages"""
        assert not discovery._is_valid_link("Python (disambiguation)")
        assert not discovery._is_valid_link("Mercury (disambiguation)")

    def test_invalid_empty_or_short_titles(self, discovery):
        """Test filtering empty or very short titles"""
        assert not discovery._is_valid_link("")
        assert not discovery._is_valid_link("A")

    def test_invalid_portal_namespace(self, discovery):
        """Test filtering Portal pages"""
        assert not discovery._is_valid_link("Portal:Technology")

    def test_invalid_user_namespace(self, discovery):
        """Test filtering User pages"""
        assert not discovery._is_valid_link("User:Example")


class TestArticleExists:
    """Tests for article_exists method"""

    def test_article_does_not_exist(self, discovery):
        """Test checking non-existent article"""
        exists, state = discovery.article_exists("Non-existent Article")
        assert exists is False
        assert state is None

    def test_article_exists_loaded_state(self, discovery, seed_article):
        """Test checking existing article in loaded state"""
        exists, state = discovery.article_exists(seed_article)
        assert exists is True
        assert state == "loaded"

    def test_article_exists_discovered_state(self, test_connection, discovery):
        """Test checking article in discovered state"""
        test_connection.execute("""
            CREATE (a:Article {
                title: 'Discovered Article',
                category: NULL,
                word_count: 0,
                expansion_state: 'discovered',
                expansion_depth: 1,
                claimed_at: NULL,
                processed_at: NULL,
                retry_count: 0
            })
        """)

        exists, state = discovery.article_exists("Discovered Article")
        assert exists is True
        assert state == "discovered"

    def test_article_exists_claimed_state(self, test_connection, discovery):
        """Test checking article in claimed state"""
        test_connection.execute("""
            CREATE (a:Article {
                title: 'Claimed Article',
                category: NULL,
                word_count: 0,
                expansion_state: 'claimed',
                expansion_depth: 1,
                claimed_at: timestamp('2026-02-08T00:00:00'),
                processed_at: NULL,
                retry_count: 0
            })
        """)

        exists, state = discovery.article_exists("Claimed Article")
        assert exists is True
        assert state == "claimed"


class TestDiscoverLinks:
    """Tests for discover_links method"""

    def test_discover_new_articles(self, discovery, seed_article):
        """Test discovering new articles from links"""
        links = ["Machine Learning", "Artificial Intelligence", "Data Science"]

        new_count = discovery.discover_links(
            source_title=seed_article, links=links, current_depth=0, max_depth=2
        )

        assert new_count == 3

    def test_filters_invalid_links(self, discovery, seed_article):
        """Test that invalid links are filtered out"""
        links = [
            "Valid Article",
            "Wikipedia:About",  # Should be filtered
            "List of examples",  # Should be filtered
            "Example (disambiguation)",  # Should be filtered
        ]

        new_count = discovery.discover_links(
            source_title=seed_article, links=links, current_depth=0, max_depth=2
        )

        # Only "Valid Article" should be discovered
        assert new_count == 1

    def test_links_to_existing_articles(self, test_connection, discovery, seed_article):
        """Test creating links to existing articles"""
        # Create existing article
        test_connection.execute("""
            CREATE (a:Article {
                title: 'Existing Article',
                category: NULL,
                word_count: 0,
                expansion_state: 'loaded',
                expansion_depth: 1,
                claimed_at: NULL,
                processed_at: timestamp('2026-02-08T00:00:00'),
                retry_count: 0
            })
        """)

        links = ["Existing Article"]

        new_count = discovery.discover_links(
            source_title=seed_article, links=links, current_depth=0, max_depth=2
        )

        # Should not discover (already exists)
        assert new_count == 0

        # But should create link
        result = test_connection.execute(
            """
            MATCH (source:Article {title: $source})-[r:LINKS_TO]->(target:Article {title: $target})
            RETURN COUNT(r) AS count
        """,
            {"source": seed_article, "target": "Existing Article"},
        )

        assert result.get_next()["count"] == 1

    def test_respects_max_depth(self, discovery, seed_article):
        """Test that max_depth is respected"""
        links = ["Should Not Discover"]

        # At max depth, should not discover
        new_count = discovery.discover_links(
            source_title=seed_article, links=links, current_depth=2, max_depth=2
        )

        assert new_count == 0

    def test_sets_correct_depth(self, test_connection, discovery, seed_article):
        """Test that discovered articles have correct depth"""
        links = ["New Article"]

        discovery.discover_links(
            source_title=seed_article, links=links, current_depth=0, max_depth=2
        )

        # Check depth
        result = test_connection.execute("""
            MATCH (a:Article {title: 'New Article'})
            RETURN a.expansion_depth AS depth
        """)

        assert result.get_next()["depth"] == 1

    def test_creates_links_to_relationship(self, test_connection, discovery, seed_article):
        """Test that LINKS_TO relationships are created"""
        links = ["Target Article"]

        discovery.discover_links(
            source_title=seed_article, links=links, current_depth=0, max_depth=2
        )

        # Check relationship
        result = test_connection.execute(
            """
            MATCH (source:Article {title: $source})-[r:LINKS_TO]->(target:Article {title: $target})
            RETURN r.link_type AS link_type
        """,
            {"source": seed_article, "target": "Target Article"},
        )

        assert result.has_next()
        assert result.get_next()["link_type"] == "internal"

    def test_handles_duplicate_links(self, test_connection, discovery, seed_article):
        """Test handling of duplicate links in list"""
        links = ["Article A", "Article A", "Article A"]

        discovery.discover_links(
            source_title=seed_article, links=links, current_depth=0, max_depth=2
        )

        # Should only create once
        # Note: First one creates, subsequent ones link to existing
        # So new_count may vary depending on order processed
        # But final state should have only one article
        result = test_connection.execute("""
            MATCH (a:Article {title: 'Article A'})
            RETURN COUNT(a) AS count
        """)

        assert result.get_next()["count"] == 1

    def test_empty_links_list(self, discovery, seed_article):
        """Test with empty links list"""
        new_count = discovery.discover_links(
            source_title=seed_article, links=[], current_depth=0, max_depth=2
        )

        assert new_count == 0

    def test_does_not_create_duplicate_relationships(
        self, test_connection, discovery, seed_article
    ):
        """Test that duplicate relationships are not created"""
        links = ["Target"]

        # Discover first time
        discovery.discover_links(
            source_title=seed_article, links=links, current_depth=0, max_depth=2
        )

        # Discover again
        discovery.discover_links(
            source_title=seed_article, links=links, current_depth=0, max_depth=2
        )

        # Should only have one relationship
        result = test_connection.execute(
            """
            MATCH (source:Article {title: $source})-[r:LINKS_TO]->(target:Article {title: $target})
            RETURN COUNT(r) AS count
        """,
            {"source": seed_article, "target": "Target"},
        )

        assert result.get_next()["count"] == 1


class TestGetDiscoveredCount:
    """Tests for get_discovered_count method"""

    def test_no_discovered_articles(self, discovery):
        """Test count with no discovered articles"""
        count = discovery.get_discovered_count()
        assert count == 0

    def test_counts_discovered_articles(self, test_connection, discovery):
        """Test counting discovered articles"""
        # Insert discovered articles
        for i in range(5):
            test_connection.execute(f"""
                CREATE (a:Article {{
                    title: 'Discovered {i}',
                    category: NULL,
                    word_count: 0,
                    expansion_state: 'discovered',
                    expansion_depth: 1,
                    claimed_at: NULL,
                    processed_at: NULL,
                    retry_count: 0
                }})
            """)

        count = discovery.get_discovered_count()
        assert count == 5

    def test_does_not_count_other_states(self, test_connection, discovery):
        """Test that only discovered state is counted"""
        states = ["loaded", "claimed", "failed"]

        for i, state in enumerate(states):
            test_connection.execute(f"""
                CREATE (a:Article {{
                    title: '{state} Article {i}',
                    category: NULL,
                    word_count: 0,
                    expansion_state: '{state}',
                    expansion_depth: 0,
                    claimed_at: NULL,
                    processed_at: timestamp('2026-02-08T00:00:00'),
                    retry_count: 0
                }})
            """)

        # Add one discovered
        test_connection.execute("""
            CREATE (a:Article {
                title: 'Discovered Article',
                category: NULL,
                word_count: 0,
                expansion_state: 'discovered',
                expansion_depth: 1,
                claimed_at: NULL,
                processed_at: NULL,
                retry_count: 0
            })
        """)

        count = discovery.get_discovered_count()
        assert count == 1


class TestIntegration:
    """Integration tests"""

    def test_full_discovery_workflow(self, test_connection, discovery, seed_article):
        """Test complete discovery workflow"""
        # Simulate fetched links from Wikipedia
        links = [
            "Machine Learning",
            "Artificial Intelligence",
            "Python Syntax",
            "Wikipedia:About",  # Invalid
            "List of languages",  # Invalid
        ]

        # Discover links
        new_count = discovery.discover_links(
            source_title=seed_article, links=links, current_depth=0, max_depth=2
        )

        # Should discover 3 valid articles
        assert new_count == 3

        # Check discovered count
        assert discovery.get_discovered_count() == 3

        # Verify all articles exist
        for title in ["Machine Learning", "Artificial Intelligence", "Python Syntax"]:
            exists, state = discovery.article_exists(title)
            assert exists
            assert state == "discovered"

        # Verify links created
        result = test_connection.execute(
            """
            MATCH (source:Article {title: $source})-[r:LINKS_TO]->(target:Article)
            RETURN COUNT(r) AS count
        """,
            {"source": seed_article},
        )

        assert result.get_next()["count"] == 3

    def test_multi_level_expansion(self, test_connection, discovery):
        """Test multi-level expansion scenario"""
        # Create depth 0 article
        test_connection.execute("""
            CREATE (a:Article {
                title: 'Depth 0',
                category: NULL,
                word_count: 0,
                expansion_state: 'loaded',
                expansion_depth: 0,
                claimed_at: NULL,
                processed_at: timestamp('2026-02-08T00:00:00'),
                retry_count: 0
            })
        """)

        # Discover at depth 1
        discovery.discover_links(
            source_title="Depth 0", links=["Depth 1 Article"], current_depth=0, max_depth=2
        )

        # Mark depth 1 as loaded
        test_connection.execute("""
            MATCH (a:Article {title: 'Depth 1 Article'})
            SET a.expansion_state = 'loaded'
        """)

        # Discover at depth 2
        discovery.discover_links(
            source_title="Depth 1 Article", links=["Depth 2 Article"], current_depth=1, max_depth=2
        )

        # Try to discover at depth 3 (should fail)
        test_connection.execute("""
            MATCH (a:Article {title: 'Depth 2 Article'})
            SET a.expansion_state = 'loaded'
        """)

        new_count = discovery.discover_links(
            source_title="Depth 2 Article", links=["Should Not Exist"], current_depth=2, max_depth=2
        )

        assert new_count == 0

        # Verify depth structure
        result = test_connection.execute("""
            MATCH (a:Article)
            RETURN a.title AS title, a.expansion_depth AS depth
            ORDER BY depth, title
        """)

        depths = {row["title"]: row["depth"] for row in result}
        assert depths["Depth 0"] == 0
        assert depths["Depth 1 Article"] == 1
        assert depths["Depth 2 Article"] == 2
        assert "Should Not Exist" not in depths
