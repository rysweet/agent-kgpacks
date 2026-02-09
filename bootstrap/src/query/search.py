"""
Query functions for WikiGR

Provides semantic search, graph traversal, and hybrid queries.
"""

import logging

import kuzu

logger = logging.getLogger(__name__)


def semantic_search(
    conn: kuzu.Connection, query_title: str, category: str | None = None, top_k: int = 10
) -> list[dict]:
    """
    Find articles semantically similar to query article

    Args:
        conn: Kuzu connection
        query_title: Title of query article
        category: Optional category filter
        top_k: Number of results to return

    Returns:
        List of results: [
            {
                'article_title': str,
                'section_title': str,
                'similarity': float,
                'rank': int
            },
            ...
        ]
    """
    logger.info(f"Semantic search for: {query_title}")

    # Step 1: Get query article's section embeddings
    query_result = conn.execute(
        """
        MATCH (a:Article {title: $query_title})-[:HAS_SECTION]->(s:Section)
        RETURN s.embedding AS embedding, s.section_id AS section_id
    """,
        {"query_title": query_title},
    )

    query_df = query_result.get_as_df()

    if len(query_df) == 0:
        logger.warning(f"Query article not found: {query_title}")
        return []

    logger.info(f"  Found {len(query_df)} query sections")

    # Step 2: For each query embedding, find similar sections
    all_matches = []

    for _idx, row in query_df.iterrows():
        query_embedding = row["embedding"]

        # Query vector index
        result = conn.execute(
            """
            CALL QUERY_VECTOR_INDEX(
                'Section',
                'embedding_idx',
                $query_embedding,
                $top_k
            ) RETURN *
        """,
            {
                "query_embedding": query_embedding,
                "top_k": top_k * 5,  # Over-fetch for aggregation
            },
        )

        matches = result.get_as_df()

        for _, match_row in matches.iterrows():
            node = match_row["node"]
            distance = match_row["distance"]

            # Extract section info (handle both dict formats)
            if isinstance(node, dict):
                if "_properties" in node:
                    section_id = node["_properties"]["section_id"]
                    section_title = node["_properties"]["title"]
                else:
                    section_id = node["section_id"]
                    section_title = node["title"]
            else:
                # Node is a Section object, access properties directly
                section_id = node.section_id
                section_title = node.title

            # Get article title from section_id
            article_title = section_id.split("#")[0]

            # Skip self-matches
            if article_title == query_title:
                continue

            all_matches.append(
                {
                    "article_title": article_title,
                    "section_title": section_title,
                    "section_id": section_id,
                    "distance": distance,
                    "similarity": 1.0 - distance,  # Convert distance to similarity
                }
            )

    # Step 3: Aggregate by article (take best matching section per article)
    article_best_matches = {}

    for match in all_matches:
        article = match["article_title"]

        if article not in article_best_matches:
            article_best_matches[article] = match
        else:
            # Keep best match (lowest distance)
            if match["distance"] < article_best_matches[article]["distance"]:
                article_best_matches[article] = match

    # Step 4: Filter by category if specified
    if category:
        filtered_matches = []

        for article_title, match in article_best_matches.items():
            # Check article category
            cat_result = conn.execute(
                """
                MATCH (a:Article {title: $title})
                RETURN a.category AS category
            """,
                {"title": article_title},
            )

            cat_df = cat_result.get_as_df()
            if len(cat_df) > 0 and cat_df.iloc[0]["category"] == category:
                filtered_matches.append(match)

        results = filtered_matches
    else:
        results = list(article_best_matches.values())

    # Step 5: Sort by similarity (descending) and take top_k
    results.sort(key=lambda x: x["similarity"], reverse=True)
    results = results[:top_k]

    # Add rank
    for i, result in enumerate(results, 1):
        result["rank"] = i

    logger.info(f"  Returning {len(results)} results")

    return results


def graph_traversal(
    conn: kuzu.Connection,
    seed_title: str,
    max_hops: int = 2,
    category: str | None = None,
    max_results: int = 50,
) -> list[dict]:
    """
    Explore articles within N hops of seed article

    Args:
        conn: Kuzu connection
        seed_title: Seed article title
        max_hops: Maximum hops to explore
        category: Optional category filter
        max_results: Maximum results to return

    Returns:
        List of neighbors: [
            {
                'article_title': str,
                'hops': int
            },
            ...
        ]
    """
    logger.info(f"Graph traversal from: {seed_title} (max_hops={max_hops})")

    # Build query dynamically
    if category:
        query = f"""
            MATCH path = (seed:Article {{title: $seed_title}})-[:LINKS_TO*1..{max_hops}]->(neighbor:Article)
            WHERE neighbor.category = $category
            RETURN DISTINCT neighbor.title AS article_title, length(path) AS hops
            ORDER BY hops ASC
            LIMIT $max_results
        """
        params = {"seed_title": seed_title, "category": category, "max_results": max_results}
    else:
        query = f"""
            MATCH path = (seed:Article {{title: $seed_title}})-[:LINKS_TO*1..{max_hops}]->(neighbor:Article)
            RETURN DISTINCT neighbor.title AS article_title, length(path) AS hops
            ORDER BY hops ASC
            LIMIT $max_results
        """
        params = {"seed_title": seed_title, "max_results": max_results}

    result = conn.execute(query, params)
    df = result.get_as_df()

    results = df.to_dict("records")

    logger.info(f"  Found {len(results)} neighbors")

    return results


def hybrid_query(
    conn: kuzu.Connection,
    seed_title: str,
    category: str | None = None,
    max_hops: int = 2,
    top_k: int = 10,
) -> list[dict]:
    """
    Hybrid query: semantic similarity + graph proximity

    Args:
        conn: Kuzu connection
        seed_title: Seed article title
        category: Optional category filter
        max_hops: Maximum hops for graph proximity
        top_k: Number of results to return

    Returns:
        List of results with combined scores
    """
    logger.info(f"Hybrid query for: {seed_title}")

    # Step 1: Semantic search (top 100)
    semantic_results = semantic_search(conn, seed_title, category=category, top_k=100)

    if not semantic_results:
        logger.warning("No semantic results found")
        return []

    # Step 2: Graph traversal (get proximate articles)
    graph_results = graph_traversal(
        conn, seed_title, max_hops=max_hops, category=category, max_results=100
    )

    if not graph_results:
        logger.warning("No graph results found")
        return semantic_results[:top_k]  # Return semantic only

    # Step 3: Find intersection (semantic AND graph-proximate)
    graph_titles = {r["article_title"]: r["hops"] for r in graph_results}

    hybrid_results = []
    for sem_result in semantic_results:
        article_title = sem_result["article_title"]

        if article_title in graph_titles:
            hops = graph_titles[article_title]

            # Combined score: 70% semantic, 30% graph proximity
            semantic_score = sem_result["similarity"]
            graph_score = 1.0 / (hops + 1)  # Closer is better

            combined_score = 0.7 * semantic_score + 0.3 * graph_score

            hybrid_results.append(
                {
                    "article_title": article_title,
                    "section_title": sem_result["section_title"],
                    "similarity": semantic_score,
                    "hops": hops,
                    "combined_score": combined_score,
                }
            )

    # Step 4: Sort by combined score
    hybrid_results.sort(key=lambda x: x["combined_score"], reverse=True)

    # Add rank
    for i, result in enumerate(hybrid_results[:top_k], 1):
        result["rank"] = i

    logger.info(f"  Returning {len(hybrid_results[:top_k])} hybrid results")

    return hybrid_results[:top_k]


def main():
    """Test query functions"""
    import kuzu

    db_path = "data/test_loader.db"
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    print("\n" + "=" * 60)
    print("Testing Semantic Search")
    print("=" * 60)

    results = semantic_search(
        conn, query_title="Python (programming language)", category="Computer Science", top_k=5
    )

    print("\nTop 5 similar articles to 'Python (programming language)':")
    for result in results:
        print(f"  {result['rank']}. {result['article_title']}")
        print(f"     Section: {result['section_title']}")
        print(f"     Similarity: {result['similarity']:.4f}")


if __name__ == "__main__":
    main()
