"""
Graph service for WikiGR visualization.

Handles graph traversal and node/edge construction.
"""

import logging
import time

import kuzu

from backend.models.graph import Edge, GraphResponse, Node

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

        # Validate seed article exists
        result = conn.execute("MATCH (a:Article {title: $title}) RETURN a", {"title": article})
        if not result.has_next():
            raise ValueError(f"Article not found: {article}")

        # Build query for graph traversal
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

        # Build nodes
        nodes = []
        node_set = set()

        for _, row in df.iterrows():
            title = row["title"]
            if title in node_set:
                continue
            node_set.add(title)

            # Get outgoing links count
            links_result = conn.execute(
                """
                MATCH (a:Article {title: $title})-[:LINKS_TO]->(target)
                RETURN count(target) AS count
                """,
                {"title": title},
            )
            links_df = links_result.get_as_df()
            links_count = int(links_df.iloc[0]["count"]) if len(links_df) > 0 else 0

            # Get summary (first section content)
            summary_result = conn.execute(
                """
                MATCH (a:Article {title: $title})-[:HAS_SECTION]->(s:Section)
                RETURN s.content AS content
                ORDER BY s.section_id ASC
                LIMIT 1
                """,
                {"title": title},
            )
            summary_df = summary_result.get_as_df()
            summary = ""
            if len(summary_df) > 0:
                content = summary_df.iloc[0]["content"]
                if content:
                    # Take first 200 characters as summary
                    summary = content[:200] + "..." if len(content) > 200 else content

            node = Node(
                id=title,
                title=title,
                category=row["category"],
                word_count=int(row["word_count"]),
                depth=int(row["depth"]),
                links_count=links_count,
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
