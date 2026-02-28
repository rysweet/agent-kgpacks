"""Auto-generate LINKS_TO edges between articles based on entity co-occurrence.

Web-sourced packs have 0 LINKS_TO edges (no hyperlinks between pages).
This module creates edges between articles that share entities, giving
the knowledge graph actual structure for GraphReranker and MultiDocSynthesizer.

Rule: Two articles get a LINKS_TO edge if they share 2+ entities.
"""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


def generate_cooccurrence_edges(conn) -> int:
    """Create LINKS_TO edges between articles sharing entities.

    Args:
        conn: Active Kuzu connection (must be writable).

    Returns:
        Number of edges created.
    """
    # Step 1: Get all article-entity pairs
    try:
        result = conn.execute(
            "MATCH (a:Article)-[:HAS_ENTITY]->(e:Entity) "
            "RETURN a.title AS article, e.name AS entity"
        )
        df = result.get_as_df()
    except Exception as e:
        logger.warning("Failed to query article-entity pairs: %s", e)
        return 0

    if df.empty:
        logger.info("No article-entity pairs found, skipping edge generation")
        return 0

    # Step 2: Build entity → articles mapping
    entity_to_articles: dict[str, set[str]] = defaultdict(set)
    for _, row in df.iterrows():
        entity_to_articles[row["entity"]].add(row["article"])

    # Step 3: Find article pairs sharing 2+ entities
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for _entity, articles in entity_to_articles.items():
        articles_list = sorted(articles)
        for i in range(len(articles_list)):
            for j in range(i + 1, len(articles_list)):
                pair = (articles_list[i], articles_list[j])
                pair_counts[pair] += 1

    # Step 4: Create edges for pairs with 2+ shared entities
    edges_created = 0
    for (src, dst), shared_count in pair_counts.items():
        if shared_count >= 2:
            try:
                # Create bidirectional edges
                conn.execute(
                    "MATCH (a:Article {title: $src}), (b:Article {title: $dst}) "
                    "CREATE (a)-[:LINKS_TO]->(b)",
                    {"src": src, "dst": dst},
                )
                conn.execute(
                    "MATCH (a:Article {title: $src}), (b:Article {title: $dst}) "
                    "CREATE (b)-[:LINKS_TO]->(a)",
                    {"src": src, "dst": dst},
                )
                edges_created += 2
            except Exception as e:
                logger.debug("Failed to create edge %s→%s: %s", src, dst, e)

    logger.info(
        "Generated %d LINKS_TO edges from %d article pairs sharing 2+ entities",
        edges_created,
        sum(1 for c in pair_counts.values() if c >= 2),
    )
    return edges_created
