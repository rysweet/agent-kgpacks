"""
Database loader for WikiGR

Integrates Wikipedia API, section parsing, and embedding generation
to load articles into Kuzu database.
"""

import logging
from datetime import datetime

import kuzu
import numpy as np

from ..embeddings import EmbeddingGenerator
from ..wikipedia import ArticleNotFoundError, WikipediaAPIClient, WikipediaArticle
from ..wikipedia.parser import parse_sections

logger = logging.getLogger(__name__)


class ArticleLoader:
    """Loads Wikipedia articles into Kuzu database"""

    def __init__(
        self,
        db_path: str,
        wikipedia_client: WikipediaAPIClient | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
    ):
        """
        Initialize article loader

        Args:
            db_path: Path to Kuzu database
            wikipedia_client: Wikipedia API client (creates default if None)
            embedding_generator: Embedding generator (creates default if None)
        """
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)

        self.wikipedia_client = wikipedia_client or WikipediaAPIClient()
        self.embedding_generator = embedding_generator or EmbeddingGenerator()

        logger.info(f"ArticleLoader initialized with database: {db_path}")

    def load_article(
        self,
        title: str,
        category: str = "General",
        expansion_state: str = "loaded",
        expansion_depth: int = 0,
    ) -> tuple[bool, str | None]:
        """
        Load a single article into database

        Args:
            title: Article title
            category: Article category
            expansion_state: State for expansion tracking
            expansion_depth: Depth in expansion tree

        Returns:
            (success, error_message)
        """
        try:
            logger.info(f"Loading article: {title}")

            # Step 1: Fetch from Wikipedia
            try:
                article = self.wikipedia_client.fetch_article(title)
            except ArticleNotFoundError:
                logger.warning(f"Article not found: {title}")
                return (False, f"Article not found: {title}")

            # Step 2: Parse sections
            sections = parse_sections(article.wikitext)

            if not sections:
                logger.warning(f"No sections found in article: {title}")
                return (False, "No sections parsed from article")

            logger.info(f"  Parsed {len(sections)} sections")

            # Step 3: Generate embeddings
            section_texts = [s["content"] for s in sections]
            embeddings = self.embedding_generator.generate(section_texts, show_progress=False)

            logger.info(f"  Generated {len(embeddings)} embeddings")

            # Step 4: Load into database (transaction)
            self._insert_article_with_sections(
                article=article,
                sections=sections,
                embeddings=embeddings,
                category=category,
                expansion_state=expansion_state,
                expansion_depth=expansion_depth,
            )

            logger.info(f"  ✓ Successfully loaded: {title}")
            return (True, None)

        except Exception as e:
            error_msg = f"Failed to load article {title}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, error_msg)

    def _insert_article_with_sections(
        self,
        article: WikipediaArticle,
        sections: list[dict],
        embeddings: np.ndarray,
        category: str,
        expansion_state: str,
        expansion_depth: int,
    ):
        """Insert article and sections in a transaction"""

        # Calculate word count
        word_count = len(article.wikitext.split())

        # Insert Article node
        self.conn.execute(
            """
            CREATE (a:Article {
                title: $title,
                category: $category,
                word_count: $word_count,
                expansion_state: $expansion_state,
                expansion_depth: $expansion_depth,
                claimed_at: NULL,
                processed_at: $now,
                retry_count: 0
            })
        """,
            {
                "title": article.title,
                "category": category,
                "word_count": word_count,
                "expansion_state": expansion_state,
                "expansion_depth": expansion_depth,
                "now": datetime.now(),
            },
        )

        # Insert Section nodes and relationships
        for i, (section, embedding) in enumerate(zip(sections, embeddings)):
            section_id = f"{article.title}#{i}"
            section_word_count = len(section["content"].split())

            # Insert Section node
            self.conn.execute(
                """
                CREATE (s:Section {
                    section_id: $section_id,
                    title: $title,
                    content: $content,
                    embedding: $embedding,
                    level: $level,
                    word_count: $word_count
                })
            """,
                {
                    "section_id": section_id,
                    "title": section["title"],
                    "content": section["content"],
                    "embedding": embedding.tolist(),
                    "level": section["level"],
                    "word_count": section_word_count,
                },
            )

            # Create HAS_SECTION relationship
            self.conn.execute(
                """
                MATCH (a:Article {title: $article_title}),
                      (s:Section {section_id: $section_id})
                CREATE (a)-[:HAS_SECTION {section_index: $index}]->(s)
            """,
                {"article_title": article.title, "section_id": section_id, "index": i},
            )

        # Insert Category node (if not exists)
        self.conn.execute(
            """
            MERGE (c:Category {name: $category})
            ON CREATE SET c.article_count = 1
            ON MATCH SET c.article_count = c.article_count + 1
        """,
            {"category": category},
        )

        # Create IN_CATEGORY relationship
        self.conn.execute(
            """
            MATCH (a:Article {title: $title}),
                  (c:Category {name: $category})
            CREATE (a)-[:IN_CATEGORY]->(c)
        """,
            {"title": article.title, "category": category},
        )

    def load_articles_batch(
        self, titles: list[str], category: str = "General"
    ) -> dict[str, tuple[bool, str | None]]:
        """
        Load multiple articles

        Args:
            titles: List of article titles
            category: Category for all articles

        Returns:
            Dictionary mapping title to (success, error_message)
        """
        results = {}

        for i, title in enumerate(titles, 1):
            logger.info(f"Loading article {i}/{len(titles)}: {title}")
            success, error = self.load_article(title, category=category)
            results[title] = (success, error)

        # Summary
        success_count = sum(1 for success, _ in results.values() if success)
        logger.info(f"Batch complete: {success_count}/{len(titles)} successful")

        return results

    def get_article_count(self) -> int:
        """Get total number of articles in database"""
        result = self.conn.execute("""
            MATCH (a:Article)
            RETURN COUNT(a) AS count
        """)
        return result.get_as_df().iloc[0]["count"]

    def get_section_count(self) -> int:
        """Get total number of sections in database"""
        result = self.conn.execute("""
            MATCH (s:Section)
            RETURN COUNT(s) AS count
        """)
        return result.get_as_df().iloc[0]["count"]

    def article_exists(self, title: str) -> bool:
        """Check if article already exists in database"""
        result = self.conn.execute(
            """
            MATCH (a:Article {title: $title})
            RETURN COUNT(a) AS count
        """,
            {"title": title},
        )
        return result.get_as_df().iloc[0]["count"] > 0


def main():
    """Test article loader"""

    print("=" * 60)
    print("Article Loader Test")
    print("=" * 60)

    # Create test database
    db_path = "data/test_loader.db"
    print(f"\nDatabase: {db_path}")

    # Initialize loader
    loader = ArticleLoader(db_path)

    # Test articles
    test_articles = [
        ("Python (programming language)", "Computer Science"),
        ("Machine Learning", "Computer Science"),
        ("Quantum Computing", "Physics"),
    ]

    print(f"\nLoading {len(test_articles)} test articles...")

    for title, category in test_articles:
        success, error = loader.load_article(title, category=category)

        if success:
            print(f"  ✓ {title}")
        else:
            print(f"  ✗ {title}: {error}")

    # Check results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Articles in database: {loader.get_article_count()}")
    print(f"Sections in database: {loader.get_section_count()}")

    # Verify data
    result = loader.conn.execute("""
        MATCH (a:Article)-[:HAS_SECTION]->(s:Section)
        RETURN a.title AS article, COUNT(s) AS sections
        ORDER BY sections DESC
    """)

    print("\nArticles with section counts:")
    df = result.get_as_df()
    for _idx, row in df.iterrows():
        print(f"  {row['article']}: {row['sections']} sections")

    print("\n✓ Test complete!")


if __name__ == "__main__":
    main()
