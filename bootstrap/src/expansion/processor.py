"""
Article processor for WikiGR expansion

Integrates all modules to process a single article:
1. Fetch from content source (Wikipedia, web, etc.)
2. Parse sections
3. Generate embeddings
4. Load into database
5. Extract links for expansion
6. Optional: LLM extraction of entities and facts
"""

import logging

import kuzu
import numpy as np

from ..embeddings import EmbeddingGenerator
from ..sources.base import Article, ArticleNotFoundError, ContentSource

logger = logging.getLogger(__name__)


def _sanitize_error(error_msg: str) -> str:
    """Sanitize error messages to remove API keys and sensitive tokens.

    Redacts common patterns:
    - API keys (alphanumeric strings 20-128 chars)
    - Bearer tokens
    - Authorization headers
    - Secret keys

    Args:
        error_msg: Original error message

    Returns:
        Sanitized error message with sensitive data redacted
    """
    import re

    # Redact API keys with = or : separators
    sanitized = re.sub(
        r"\b(api[_-]?key|token|secret[_-]?key|bearer|authorization)[=:\s]+['\"]?([a-zA-Z0-9_-]{20,128})['\"]?",
        r"\1=***REDACTED***",
        error_msg,
        flags=re.IGNORECASE,
    )

    # Redact standalone API keys (sk-..., any 20+ char alphanumeric string in quotes or after 'key'/'token')
    sanitized = re.sub(
        r"(['\"])(sk-[a-zA-Z0-9_-]{20,128}|[a-zA-Z0-9_-]{30,128})(['\"])",
        r"\1***REDACTED***\3",
        sanitized,
    )

    # Redact Authorization headers
    sanitized = re.sub(
        r"(Authorization:\s*)(Bearer\s+)?[a-zA-Z0-9_-]+",
        r"\1***REDACTED***",
        sanitized,
        flags=re.IGNORECASE,
    )

    # Redact dict-style API keys {"api_key": "value"}
    sanitized = re.sub(
        r'(["\']api[_-]?key["\']\s*:\s*["\'])([a-zA-Z0-9_-]{20,128})(["\'])',
        r"\1***REDACTED***\3",
        sanitized,
        flags=re.IGNORECASE,
    )

    return sanitized


class ArticleProcessor:
    """Processes articles for expansion"""

    def __init__(
        self,
        conn: kuzu.Connection,
        content_source: ContentSource | None = None,
        wikipedia_client=None,  # Backward compatibility
        embedding_generator: EmbeddingGenerator | None = None,
        llm_extractor=None,  # Optional LLM extraction
    ):
        """
        Initialize article processor

        Args:
            conn: Kuzu database connection
            content_source: ContentSource implementation (Wikipedia, web, etc.)
            wikipedia_client: Deprecated - use content_source instead
            embedding_generator: Embedding generator
            llm_extractor: Optional LLM extractor for entities/facts
        """
        self.conn = conn

        # Handle backward compatibility
        if content_source is None and wikipedia_client is not None:
            # Legacy path: wrap wikipedia_client
            from ..sources.wikipedia_source import WikipediaContentSource

            self.content_source = WikipediaContentSource(client=wikipedia_client)
        elif content_source is None:
            # Default to Wikipedia
            from ..sources.wikipedia_source import WikipediaContentSource

            self.content_source = WikipediaContentSource()
        else:
            self.content_source = content_source

        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self.llm_extractor = llm_extractor

        logger.info("ArticleProcessor initialized")

    def process_article(
        self, title_or_url: str, category: str = "General", expansion_depth: int = 0
    ) -> tuple[bool, list[str], str | None]:
        """
        Process a single article: fetch, parse, embed, load

        Args:
            title_or_url: Article title (Wikipedia) or URL (web)
            category: Article category
            expansion_depth: Depth in expansion tree

        Returns:
            (success, links, error_message)
            - success: True if loaded successfully
            - links: List of linked article titles/URLs (for expansion)
            - error_message: None if success, error string if failed
        """
        try:
            logger.info(f"Processing article: {title_or_url} (depth={expansion_depth})")

            # Step 1: Fetch from content source
            try:
                article: Article = self.content_source.fetch_article(title_or_url)
                logger.info(f"  Fetched: {len(article.content)} chars from {article.source_type}")
            except ArticleNotFoundError:
                error_msg = f"Article not found: {title_or_url}"
                logger.warning(_sanitize_error(error_msg))
                return (False, [], error_msg)

            # Step 2: Handle Wikipedia redirects
            import re

            if article.source_type == "wikipedia":
                redirect_match = re.match(
                    r"#REDIRECT\s*\[\[(.+?)\]\]", article.content, re.IGNORECASE
                )
                if redirect_match:
                    redirect_target = redirect_match.group(1)
                    logger.info(f"  Redirect: {title_or_url} -> {redirect_target}")
                    try:
                        article = self.content_source.fetch_article(redirect_target)
                        logger.info(f"  Fetched redirect target: {len(article.content)} chars")
                    except ArticleNotFoundError:
                        logger.info(f"  Skipping unfollowable redirect: {title_or_url}")
                        return (True, [], None)
                    except Exception as e:
                        error_msg = f"Redirect target fetch failed: {e}"
                        logger.warning(f"  {_sanitize_error(error_msg)}")
                        return (False, [], error_msg)

            # Parse sections
            sections = self.content_source.parse_sections(article.content)

            if not sections:
                logger.info(f"  Skipping stub article (no sections): {title_or_url}")
                return (True, article.links, None)

            logger.info(f"  Parsed {len(sections)} sections")

            # Step 3: Generate embeddings
            section_texts = [s["content"] for s in sections]
            embeddings = self.embedding_generator.generate(section_texts, show_progress=False)

            logger.info(f"  Generated {len(embeddings)} embeddings")

            # Step 4: Optional LLM extraction
            extraction_result = None
            if self.llm_extractor is not None:
                try:
                    extraction_result = self.llm_extractor.extract_from_article(
                        title=article.title,
                        sections=sections,
                        max_sections=5,
                        domain=self._detect_domain(article.categories),
                    )
                    logger.info(
                        f"  Extracted {len(extraction_result.entities)} entities, {len(extraction_result.relationships)} relationships"
                    )
                except Exception as e:
                    # LLM extraction is optional - don't fail article processing
                    logger.warning(
                        f"  LLM extraction failed (continuing): {_sanitize_error(str(e))}"
                    )

            # Step 5: Load into database
            self._insert_article_with_sections(
                article=article,
                sections=sections,
                embeddings=embeddings,
                category=category,
                expansion_depth=expansion_depth,
                extraction_result=extraction_result,
            )

            logger.info(f"  ✓ Successfully loaded: {article.title}")

            # Return success with links for expansion
            return (True, article.links, None)

        except Exception as e:
            error_msg = f"Processing error: {str(e)}"
            logger.error(
                f"  ✗ Failed to process {title_or_url}: {_sanitize_error(error_msg)}", exc_info=True
            )
            return (False, [], error_msg)

    def _detect_domain(self, categories: list[str]) -> str | None:
        """Detect article domain from categories."""
        try:
            from ..extraction.llm_extractor import detect_domain

            return detect_domain(categories)
        except ImportError:
            return None

    def _insert_article_with_sections(
        self,
        article: Article,
        sections: list[dict],
        embeddings: np.ndarray,
        category: str,
        expansion_depth: int,
        extraction_result=None,
    ):
        """Insert article and sections into database.

        Note: Explicit transactions are not used here because Kuzu's
        single-connection model auto-commits each statement. Using
        BEGIN TRANSACTION would conflict with work queue writes on
        the same connection (write-write conflict).
        """
        from datetime import datetime, timezone

        self._do_insert_article_with_sections(
            article,
            sections,
            embeddings,
            category,
            expansion_depth,
            datetime.now(tz=timezone.utc),
            extraction_result,
        )

    def _do_insert_article_with_sections(
        self,
        article: Article,
        sections: list[dict],
        embeddings: np.ndarray,
        category: str,
        expansion_depth: int,
        now,
        extraction_result=None,
    ):
        """Internal: execute all insert queries within the current transaction."""
        # Calculate word count
        word_count = len(article.content.split())

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
                    "now": now,
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
                    "now": now,
                },
            )

        # Always delete existing sections before (re)inserting to prevent
        # duplicate primary key errors from partial inserts or retries
        self.conn.execute(
            """
            MATCH (a:Article {title: $title})-[r:HAS_SECTION]->(s:Section)
            DELETE r, s
        """,
            {"title": article.title},
        )

        # Insert Section nodes with HAS_SECTION relationships in a single
        # query per section (avoids 2N queries by combining CREATE + relationship)
        for i, (section, embedding) in enumerate(zip(sections, embeddings)):
            section_id = f"{article.title}#{i}"
            section_word_count = len(section["content"].split())

            self.conn.execute(
                """
                MATCH (a:Article {title: $article_title})
                CREATE (a)-[:HAS_SECTION {section_index: $index}]->(s:Section {
                    section_id: $section_id,
                    title: $title,
                    content: $content,
                    embedding: $embedding,
                    level: $level,
                    word_count: $word_count
                })
            """,
                {
                    "article_title": article.title,
                    "section_id": section_id,
                    "title": section["title"],
                    "content": section["content"],
                    "embedding": embedding.tolist(),
                    "level": section["level"],
                    "word_count": section_word_count,
                    "index": i,
                },
            )

        # Create text chunks for fine-grained retrieval
        try:
            from ..embeddings.chunker import chunk_sections

            chunks = chunk_sections(sections, article.title)
            if chunks:
                # Delete existing chunks for this article
                self.conn.execute(
                    "MATCH (a:Article {title: $title})-[r:HAS_CHUNK]->(c:Chunk) DELETE r, c",
                    {"title": article.title},
                )

                # Generate chunk embeddings
                chunk_texts = [c.content for c in chunks]
                chunk_embeddings = self.embedding_generator.generate(
                    chunk_texts, show_progress=False
                )

                # Insert chunks with relationships
                for chunk, chunk_emb in zip(chunks, chunk_embeddings):
                    self.conn.execute(
                        """
                        MATCH (a:Article {title: $article_title})
                        CREATE (a)-[:HAS_CHUNK {section_index: $section_index, chunk_index: $chunk_index}]->(c:Chunk {
                            chunk_id: $chunk_id,
                            content: $content,
                            embedding: $embedding,
                            article_title: $article_title,
                            section_index: $section_index,
                            chunk_index: $chunk_index
                        })
                    """,
                        {
                            "article_title": article.title,
                            "chunk_id": chunk.chunk_id,
                            "content": chunk.content,
                            "embedding": chunk_emb.tolist(),
                            "section_index": chunk.section_index,
                            "chunk_index": chunk.chunk_index,
                        },
                    )
                logger.info(f"  Created {len(chunks)} chunks for {article.title}")
        except Exception as e:
            # Chunk creation is optional — don't fail article processing
            logger.debug(f"  Chunk creation skipped: {e}")

        # Clean up existing IN_CATEGORY relationships before re-creating
        # (prevents duplicate edges on retry/reprocess)
        self.conn.execute(
            """
            MATCH (a:Article {title: $title})-[r:IN_CATEGORY]->()
            DELETE r
        """,
            {"title": article.title},
        )

        # Handle categories (MERGE pattern — same as loader.py)
        for cat in article.categories[:3]:  # Limit to 3 main categories
            self.conn.execute(
                """
                MERGE (c:Category {name: $category})
                ON CREATE SET c.article_count = 1
                ON MATCH SET c.article_count = c.article_count + 1
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

        # Step 6: Insert LLM extracted entities, facts, and relationships
        if extraction_result is not None:
            try:
                # Delete existing entities/facts/relationships for this article
                self.conn.execute(
                    """
                    MATCH (a:Article {title: $title})-[r:HAS_ENTITY]->(e:Entity)
                    DELETE r
                    """,
                    {"title": article.title},
                )
                self.conn.execute(
                    """
                    MATCH (a:Article {title: $title})-[r:HAS_FACT]->(f:Fact)
                    DELETE r
                    """,
                    {"title": article.title},
                )

                # Insert entities
                entity_map = {}  # Map entity names to entity_ids for relationships
                for entity in extraction_result.entities:
                    entity_id = f"{article.title}|{entity.name}"
                    entity_map[entity.name] = entity_id

                    # Get description from properties or use empty string
                    description = entity.properties.get("description", "")

                    # MERGE to avoid duplicates
                    self.conn.execute(
                        """
                        MERGE (e:Entity {entity_id: $entity_id})
                        ON CREATE SET e.name = $name, e.type = $type, e.description = $description
                        """,
                        {
                            "entity_id": entity_id,
                            "name": entity.name,
                            "type": entity.type,
                            "description": description,
                        },
                    )

                    # Link article to entity
                    self.conn.execute(
                        """
                        MATCH (a:Article {title: $title}), (e:Entity {entity_id: $entity_id})
                        CREATE (a)-[:HAS_ENTITY]->(e)
                        """,
                        {"title": article.title, "entity_id": entity_id},
                    )

                logger.info(f"  Inserted {len(extraction_result.entities)} entities")

                # Insert facts
                for i, fact_content in enumerate(extraction_result.key_facts):
                    fact_id = f"{article.title}|fact{i}"
                    self.conn.execute(
                        """
                        MERGE (f:Fact {fact_id: $fact_id})
                        ON CREATE SET f.content = $content
                        """,
                        {"fact_id": fact_id, "content": fact_content},
                    )

                    # Link article to fact
                    self.conn.execute(
                        """
                        MATCH (a:Article {title: $title}), (f:Fact {fact_id: $fact_id})
                        CREATE (a)-[:HAS_FACT]->(f)
                        """,
                        {"title": article.title, "fact_id": fact_id},
                    )

                logger.info(f"  Inserted {len(extraction_result.key_facts)} facts")

                # Insert relationships between entities
                for rel in extraction_result.relationships:
                    source_id = entity_map.get(rel.source)
                    target_id = entity_map.get(rel.target)

                    if source_id and target_id:
                        self.conn.execute(
                            """
                            MATCH (e1:Entity {entity_id: $source_id}), (e2:Entity {entity_id: $target_id})
                            CREATE (e1)-[:ENTITY_RELATION {relation: $relation, context: $context}]->(e2)
                            """,
                            {
                                "source_id": source_id,
                                "target_id": target_id,
                                "relation": rel.relation,
                                "context": rel.context,
                            },
                        )

                logger.info(
                    f"  Inserted {len(extraction_result.relationships)} entity relationships"
                )

            except Exception as e:
                # LLM extraction is optional — don't fail article processing
                logger.warning(f"  Failed to insert LLM extracted data: {_sanitize_error(str(e))}")
