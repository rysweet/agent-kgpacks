"""
Article processor for WikiGR expansion

Integrates all modules to process a single article:
1. Fetch from Wikipedia
2. Parse sections
3. Generate embeddings
4. Load into database
5. Extract links for expansion
"""

import logging

import kuzu
import numpy as np

from ..embeddings import EmbeddingGenerator
from ..wikipedia import ArticleNotFoundError, WikipediaAPIClient
from ..wikipedia.parser import parse_sections

logger = logging.getLogger(__name__)


class ArticleProcessor:
    """Processes articles for expansion"""

    def __init__(
        self,
        conn: kuzu.Connection,
        wikipedia_client: WikipediaAPIClient | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
    ):
        """
        Initialize article processor

        Args:
            conn: Kuzu database connection
            wikipedia_client: Wikipedia API client
            embedding_generator: Embedding generator
        """
        self.conn = conn
        self.wikipedia_client = wikipedia_client or WikipediaAPIClient()
        self.embedding_generator = embedding_generator or EmbeddingGenerator()

        logger.info("ArticleProcessor initialized")

    def process_article(
        self, title: str, category: str = "General", expansion_depth: int = 0
    ) -> tuple[bool, list[str], str | None]:
        """
        Process a single article: fetch, parse, embed, load

        Args:
            title: Article title
            category: Article category
            expansion_depth: Depth in expansion tree

        Returns:
            (success, links, error_message)
            - success: True if loaded successfully
            - links: List of linked article titles (for expansion)
            - error_message: None if success, error string if failed
        """
        try:
            logger.info(f"Processing article: {title} (depth={expansion_depth})")

            # Step 1: Fetch from Wikipedia
            try:
                article = self.wikipedia_client.fetch_article(title)
                logger.info(f"  Fetched: {len(article.wikitext)} chars")
            except ArticleNotFoundError:
                error_msg = f"Article not found: {title}"
                logger.warning(error_msg)
                return (False, [], error_msg)

            # Step 2: Parse sections
            sections = parse_sections(article.wikitext)

            if not sections:
                error_msg = f"No sections parsed from article: {title}"
                logger.warning(error_msg)
                return (False, article.links, error_msg)

            logger.info(f"  Parsed {len(sections)} sections")

            # Step 3: Generate embeddings
            section_texts = [s["content"] for s in sections]
            embeddings = self.embedding_generator.generate(section_texts, show_progress=False)

            logger.info(f"  Generated {len(embeddings)} embeddings")

            # Step 4: Load into database
            self._insert_article_with_sections(
                article=article,
                sections=sections,
                embeddings=embeddings,
                category=category,
                expansion_depth=expansion_depth,
            )

            logger.info(f"  ✓ Successfully loaded: {title}")

            # Return success with links for expansion
            return (True, article.links, None)

        except Exception as e:
            error_msg = f"Processing error: {str(e)}"
            logger.error(f"  ✗ Failed to process {title}: {error_msg}", exc_info=True)
            return (False, [], error_msg)

    def _insert_article_with_sections(
        self, article, sections: list[dict], embeddings: np.ndarray, category: str, expansion_depth: int
    ):
        """Insert article and sections into database"""
        from datetime import datetime

        # Calculate word count
        word_count = len(article.wikitext.split())

        # Check if article already exists
        result = self.conn.execute(
            """
            MATCH (a:Article {title: $title})
            RETURN COUNT(a) AS count
        """,
            {"title": article.title},
        )

        article_exists = result.get_as_df().iloc[0]["count"] > 0

        if article_exists:
            # Article exists (probably a seed stub), update it
            logger.info(f"Article exists, updating: {article.title}")
            self.conn.execute(
                """
                MATCH (a:Article {title: $title})
                SET a.word_count = $word_count,
                    a.category = $category,
                    a.expansion_state = 'loaded',
                    a.processed_at = $now
            """,
                {
                    "title": article.title,
                    "word_count": word_count,
                    "category": category,
                    "now": datetime.now(),
                },
            )
        else:
            # Insert new Article node
            self.conn.execute(
                """
                CREATE (a:Article {
                    title: $title,
                    category: $category,
                    word_count: $word_count,
                    expansion_state: 'loaded',
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

        # Handle categories
        for cat in article.categories[:3]:  # Limit to 3 main categories
            # Create category if not exists
            cat_result = self.conn.execute(
                """
                MATCH (c:Category {name: $category})
                RETURN COUNT(c) AS count
            """,
                {"category": cat},
            )

            if cat_result.get_as_df().iloc[0]["count"] == 0:
                self.conn.execute(
                    """
                    CREATE (c:Category {
                        name: $category,
                        article_count: 0
                    })
                """,
                    {"category": cat},
                )

            # Create IN_CATEGORY relationship
            self.conn.execute(
                """
                MATCH (a:Article {title: $title}),
                      (c:Category {name: $category})
                CREATE (a)-[:IN_CATEGORY]->(c)
            """,
                {"title": article.title, "category": cat},
            )


def main():
    """Test article processor"""
    import shutil
    from pathlib import Path

    import kuzu

    print("=" * 60)
    print("Article Processor Test")
    print("=" * 60)

    # Create test database
    db_path = "data/test_processor.db"
    if Path(db_path).exists():
        if Path(db_path).is_dir():
            shutil.rmtree(db_path)
        else:
            Path(db_path).unlink()

    # Create schema
    from bootstrap.schema.ryugraph_schema import create_schema

    create_schema(db_path)

    # Connect
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # Initialize processor
    processor = ArticleProcessor(conn)

    # Test articles
    test_articles = [
        ("Python (programming language)", "Computer Science", 0),
        ("Artificial intelligence", "Computer Science", 0),
    ]

    print(f"\nProcessing {len(test_articles)} articles...")

    for title, category, depth in test_articles:
        print(f"\n[{title}]")
        success, links, error = processor.process_article(title, category, depth)

        if success:
            print("  ✓ Success")
            print(f"  Links found: {len(links)}")
            print(f"  Sample links: {links[:5]}")
        else:
            print(f"  ✗ Failed: {error}")

    # Check database
    result = conn.execute("""
        MATCH (a:Article)
        RETURN COUNT(a) AS articles
    """)
    print(f"\nTotal articles in database: {result.get_as_df().iloc[0]['articles']}")

    # Cleanup
    if Path(db_path).exists():
        if Path(db_path).is_dir():
            shutil.rmtree(db_path)
        else:
            Path(db_path).unlink()

    print("\n✓ Test complete!")


if __name__ == "__main__":
    main()
