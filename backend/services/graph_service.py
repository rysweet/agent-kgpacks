"""
Graph service for WikiGR visualization.

Handles graph traversal and node/edge construction.
"""

import logging
import time

import kuzu

from backend.models.graph import Edge, GraphResponse, Node
from backend.services.summary_utils import get_article_summaries

logger = logging.getLogger(__name__)


class GraphService:
    """Service for graph operations."""

    @staticmethod
    def get_graph_neighbors(
        conn: kuzu.Connection,
        article: str,
        depth: int = 2,
        limit: int = 50,
        category: str | None = None,
    ) -> GraphResponse:
        """
        Get graph structure around seed article.

        Args:
            conn: Kuzu connection
            article: Seed article title
            depth: Maximum depth to traverse (1-3)
            limit: Maximum number of nodes to return (1-200)
            category: Optional category filter

        Returns:
            GraphResponse with nodes and edges

        Raises:
            ValueError: If article not found or invalid parameters
        """
        start_time = time.time()

        # Validate depth strictly instead of silently clamping, so callers
        # receive clear feedback when they pass an out-of-range value.
        depth = int(depth)
        if depth < 1 or depth > 3:
            raise ValueError(f"depth must be between 1 and 3, got {depth}")

        # Validate seed article exists
        result = conn.execute("MATCH (a:Article {title: $title}) RETURN a", {"title": article})
        if not result.has_next():
            raise ValueError(f"Article not found: {article}")

        # Build query for graph traversal.
        # NOTE: depth is interpolated via f-string because Kuzu does not
        # support parameterised variable-length path bounds (e.g. *0..$depth).
        # The value is validated to int 1-3 above, so injection is not possible.
        if category:
            query = f"""
                MATCH path = (seed:Article {{title: $seed}})-[:LINKS_TO*0..{depth}]->(neighbor:Article)
                WHERE neighbor.category = $category
                WITH seed, neighbor, length(path) AS depth
                ORDER BY depth ASC, neighbor.title ASC
                LIMIT $limit
                RETURN
                    neighbor.title AS title,
                    neighbor.category AS category,
                    neighbor.word_count AS word_count,
                    depth
            """
            params = {"seed": article, "category": category, "limit": limit}
        else:
            query = f"""
                MATCH path = (seed:Article {{title: $seed}})-[:LINKS_TO*0..{depth}]->(neighbor:Article)
                WITH seed, neighbor, length(path) AS depth
                ORDER BY depth ASC, neighbor.title ASC
                LIMIT $limit
                RETURN
                    neighbor.title AS title,
                    neighbor.category AS category,
                    neighbor.word_count AS word_count,
                    depth
            """
            params = {"seed": article, "limit": limit}

        # Execute query
        result = conn.execute(query, params)
        df = result.get_as_df()

        # Build deduplicated node data, preserving traversal order
        nodes = []
        node_set = set()
        node_rows = []

        for _, row in df.iterrows():
            title = row["title"]
            if title in node_set:
                continue
            node_set.add(title)
            node_rows.append(row)

        titles = [row["title"] for row in node_rows]

        # Batch query for link counts (replaces N individual queries)
        link_counts: dict[str, int] = {}
        if titles:
            links_result = conn.execute(
                """
                MATCH (a:Article)-[:LINKS_TO]->(t:Article)
                WHERE a.title IN $titles
                RETURN a.title AS title, COUNT(t) AS links
                """,
                {"titles": titles},
            )
            for _, lrow in links_result.get_as_df().iterrows():
                link_counts[lrow["title"]] = int(lrow["links"])

        # Batch query for summaries (shared helper avoids duplicated logic)
        summaries = get_article_summaries(conn, titles) if titles else {}

        # Assemble node objects from batch results
        for row in node_rows:
            title = row["title"]
            summary = summaries.get(title, "")
            node = Node(
                id=title,
                title=title,
                category=row["category"],
                word_count=int(row["word_count"]),
                depth=int(row["depth"]),
                links_count=link_counts.get(title, 0),
                summary=summary,
            )
            nodes.append(node)

        # Build edges
        edges = []
        edge_set = set()

        # Get edges between nodes in our result set
        node_titles = list(node_set)
        if len(node_titles) > 1:
            # Query for edges between our nodes
            edges_query = """
                MATCH (source:Article)-[link:LINKS_TO]->(target:Article)
                WHERE source.title IN $titles AND target.title IN $titles
                RETURN source.title AS source, target.title AS target
            """
            edges_result = conn.execute(edges_query, {"titles": node_titles})
            edges_df = edges_result.get_as_df()

            for _, row in edges_df.iterrows():
                source = row["source"]
                target = row["target"]
                edge_key = (source, target)

                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    edge = Edge(
                        source=source,
                        target=target,
                        type="internal",
                        weight=1.0,
                    )
                    edges.append(edge)

        execution_time_ms = (time.time() - start_time) * 1000

        return GraphResponse(
            seed=article,
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
            execution_time_ms=execution_time_ms,
        )
