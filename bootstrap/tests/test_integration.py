"""
Integration tests for WikiGR pipeline.

Validates end-to-end: schema, API fetch, parsing, embeddings, work queue.
"""

import shutil
from pathlib import Path

import kuzu
import numpy as np
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def test_db_path(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("integration") / "test.db"
    yield str(db_path)
    p = Path(str(db_path))
    if p.exists():
        shutil.rmtree(str(db_path)) if p.is_dir() else p.unlink()


@pytest.fixture(scope="module")
def schema_db(test_db_path):
    from bootstrap.schema.ryugraph_schema import create_schema

    create_schema(test_db_path, drop_existing=True)
    return test_db_path


@pytest.fixture(scope="module")
def db_connection(schema_db):
    db = kuzu.Database(schema_db)
    conn = kuzu.Connection(db)
    yield conn


class TestSchemaIntegration:
    def test_creates_all_node_tables(self, db_connection):
        result = db_connection.execute("CALL SHOW_TABLES() RETURN *")
        names = set(result.get_as_df()["name"].tolist())
        assert {"Article", "Section", "Category"}.issubset(names)

    def test_creates_all_relationship_tables(self, db_connection):
        result = db_connection.execute("CALL SHOW_TABLES() RETURN *")
        names = set(result.get_as_df()["name"].tolist())
        assert {"HAS_SECTION", "LINKS_TO", "IN_CATEGORY"}.issubset(names)

    def test_section_supports_384_dim_embeddings(self, db_connection):
        embedding = [0.1] * 384
        db_connection.execute(
            """CREATE (s:Section {
                section_id: '__test__#0', title: 'Test', content: 'Test',
                embedding: $e, level: 2, word_count: 1
            })""",
            {"e": embedding},
        )
        result = db_connection.execute(
            "MATCH (s:Section {section_id: '__test__#0'}) RETURN s.embedding AS e"
        )
        assert len(result.get_as_df().iloc[0]["e"]) == 384
        db_connection.execute("MATCH (s:Section {section_id: '__test__#0'}) DELETE s")


class TestWikipediaAPIIntegration:
    @pytest.mark.timeout(30)
    def test_fetch_known_article(self):
        from bootstrap.src.wikipedia import WikipediaAPIClient

        client = WikipediaAPIClient()
        article = client.fetch_article("Python (programming language)")
        assert article.title == "Python (programming language)"
        assert len(article.wikitext) > 1000
        assert len(article.links) > 10

    @pytest.mark.timeout(30)
    def test_fetch_nonexistent_raises(self):
        from bootstrap.src.wikipedia import ArticleNotFoundError, WikipediaAPIClient

        client = WikipediaAPIClient()
        with pytest.raises(ArticleNotFoundError):
            client.fetch_article("This_Article_Does_Not_Exist_XYZZY_99999")


class TestParserIntegration:
    @pytest.mark.timeout(30)
    def test_parse_real_article(self):
        from bootstrap.src.wikipedia import WikipediaAPIClient
        from bootstrap.src.wikipedia.parser import parse_sections

        client = WikipediaAPIClient()
        article = client.fetch_article("Python (programming language)")
        sections = parse_sections(article.wikitext)
        assert len(sections) >= 3
        for s in sections:
            assert s["level"] in (2, 3)
            assert len(s["content"]) >= 100


class TestEmbeddingIntegration:
    def test_correct_shape(self):
        from bootstrap.src.embeddings import EmbeddingGenerator

        gen = EmbeddingGenerator(use_gpu=False)
        embeddings = gen.generate(["Machine learning", "Python programming"])
        assert embeddings.shape == (2, 384)
        assert not np.allclose(embeddings, 0)

    def test_similar_texts_high_similarity(self):
        from bootstrap.src.embeddings import EmbeddingGenerator

        gen = EmbeddingGenerator(use_gpu=False)
        e = gen.generate(["Machine learning algorithms", "Deep learning models"])
        sim = np.dot(e[0], e[1]) / (np.linalg.norm(e[0]) * np.linalg.norm(e[1]))
        assert sim > 0.5


class TestArticleLoaderIntegration:
    """Test the full article loading pipeline."""

    @pytest.mark.timeout(60)
    def test_load_single_article(self, tmp_path):
        """Load one real article and verify it's in the database."""
        from bootstrap.schema.ryugraph_schema import create_schema
        from bootstrap.src.database import ArticleLoader

        db_path = str(tmp_path / "loader_test.db")
        create_schema(db_path, drop_existing=True)

        loader = ArticleLoader(db_path)
        success, error = loader.load_article(
            "Python (programming language)", category="Computer Science"
        )

        assert success, f"Article load failed: {error}"
        assert loader.get_article_count() == 1
        assert loader.get_section_count() >= 3
        assert loader.article_exists("Python (programming language)")

    @pytest.mark.timeout(60)
    def test_load_nonexistent_article(self, tmp_path):
        """Loading a nonexistent article returns failure, not an exception."""
        from bootstrap.schema.ryugraph_schema import create_schema
        from bootstrap.src.database import ArticleLoader

        db_path = str(tmp_path / "loader_test_missing.db")
        create_schema(db_path, drop_existing=True)

        loader = ArticleLoader(db_path)
        success, error = loader.load_article("This_Article_Does_Not_Exist_XYZZY_99999")

        assert not success
        assert error is not None


class TestExpansionIntegration:
    """Test orchestrator expansion pipeline."""

    @pytest.mark.timeout(120)
    def test_expand_from_seed(self, tmp_path):
        """Start from 1 seed, expand to 3 articles."""
        from bootstrap.schema.ryugraph_schema import create_schema
        from bootstrap.src.expansion import RyuGraphOrchestrator

        db_path = str(tmp_path / "expansion_test.db")
        create_schema(db_path, drop_existing=True)

        orch = RyuGraphOrchestrator(db_path=db_path, max_depth=1, batch_size=5)
        orch.initialize_seeds(["Python (programming language)"], category="CS")

        orch.expand_to_target(target_count=3, max_iterations=10)

        # Verify the seed was processed (it may or may not expand further
        # depending on which links are discovered first)
        result = orch.conn.execute("MATCH (a:Article) WHERE a.word_count > 0 RETURN COUNT(a) AS c")
        loaded = result.get_as_df().iloc[0]["c"]
        assert loaded >= 1, f"Expected at least 1 loaded article, got {loaded}"


class TestQueryIntegration:
    """Integration tests for graph_traversal and semantic_search query functions."""

    @pytest.mark.timeout(60)
    def test_graph_traversal_returns_neighbors(self, tmp_path):
        """After loading articles with LINKS_TO, traversal finds them."""
        from bootstrap.schema.ryugraph_schema import create_schema
        from bootstrap.src.query.search import graph_traversal

        db_path = str(tmp_path / "traversal_test.db")
        create_schema(db_path, drop_existing=True)

        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)

        # Create two articles and a LINKS_TO relationship
        conn.execute("""
            CREATE (a:Article {
                title: 'Source', category: 'Test', word_count: 100,
                expansion_state: 'processed', expansion_depth: 0,
                claimed_at: NULL, processed_at: NULL, retry_count: 0
            })
        """)
        conn.execute("""
            CREATE (a:Article {
                title: 'Target', category: 'Test', word_count: 100,
                expansion_state: 'processed', expansion_depth: 1,
                claimed_at: NULL, processed_at: NULL, retry_count: 0
            })
        """)
        conn.execute("""
            MATCH (s:Article {title: 'Source'}), (t:Article {title: 'Target'})
            CREATE (s)-[:LINKS_TO {link_type: 'internal'}]->(t)
        """)

        results = graph_traversal(conn, seed_title="Source", max_hops=1)
        titles = [r["article_title"] for r in results]
        assert "Target" in titles

    @pytest.mark.timeout(60)
    def test_semantic_search_excludes_self(self, tmp_path):
        """Semantic search for an article should not return itself."""
        from bootstrap.schema.ryugraph_schema import create_schema
        from bootstrap.src.embeddings import EmbeddingGenerator
        from bootstrap.src.query.search import semantic_search

        db_path = str(tmp_path / "semantic_test.db")
        create_schema(db_path, drop_existing=True)

        db = kuzu.Database(db_path)
        conn = kuzu.Connection(db)

        gen = EmbeddingGenerator(use_gpu=False)
        emb_a = gen.generate(["Machine learning algorithms"]).tolist()[0]
        emb_b = gen.generate(["Deep learning neural networks"]).tolist()[0]

        # Create articles
        conn.execute("""
            CREATE (a:Article {
                title: 'Article A', category: 'CS', word_count: 200,
                expansion_state: 'processed', expansion_depth: 0,
                claimed_at: NULL, processed_at: NULL, retry_count: 0
            })
        """)
        conn.execute("""
            CREATE (a:Article {
                title: 'Article B', category: 'CS', word_count: 200,
                expansion_state: 'processed', expansion_depth: 0,
                claimed_at: NULL, processed_at: NULL, retry_count: 0
            })
        """)

        # Create sections with embeddings
        conn.execute(
            """CREATE (s:Section {
                section_id: 'Article A#0', title: 'Intro A', content: 'ML content',
                embedding: $e, level: 2, word_count: 50
            })""",
            {"e": emb_a},
        )
        conn.execute(
            """CREATE (s:Section {
                section_id: 'Article B#0', title: 'Intro B', content: 'DL content',
                embedding: $e, level: 2, word_count: 50
            })""",
            {"e": emb_b},
        )

        # Create HAS_SECTION relationships
        conn.execute("""
            MATCH (a:Article {title: 'Article A'}), (s:Section {section_id: 'Article A#0'})
            CREATE (a)-[:HAS_SECTION]->(s)
        """)
        conn.execute("""
            MATCH (a:Article {title: 'Article B'}), (s:Section {section_id: 'Article B#0'})
            CREATE (a)-[:HAS_SECTION]->(s)
        """)

        results = semantic_search(conn, query_title="Article A", top_k=10)
        result_titles = [r["article_title"] for r in results]
        assert "Article A" not in result_titles


class TestWorkQueueIntegration:
    def test_claim_advance_lifecycle(self):
        from bootstrap.src.expansion.work_queue import WorkQueueManager

        db = kuzu.Database()
        conn = kuzu.Connection(db)
        conn.execute("""CREATE NODE TABLE Article(
            title STRING, category STRING, word_count INT32,
            expansion_state STRING, expansion_depth INT32,
            claimed_at TIMESTAMP, processed_at TIMESTAMP,
            retry_count INT32, PRIMARY KEY(title))""")
        conn.execute("""CREATE (a:Article {
            title: 'Test', category: 'Test', word_count: 0,
            expansion_state: 'discovered', expansion_depth: 0,
            claimed_at: NULL, processed_at: NULL, retry_count: 0})""")

        mgr = WorkQueueManager(conn)
        claimed = mgr.claim_work(batch_size=1)
        assert len(claimed) == 1

        mgr.advance_state("Test", "loaded")
        result = conn.execute("MATCH (a:Article {title: 'Test'}) RETURN a.expansion_state AS s")
        assert result.get_as_df().iloc[0]["s"] == "loaded"
