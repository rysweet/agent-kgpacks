"""
Shared utility for fetching article summaries from the graph database.

Provides a batch query helper used by both GraphService and SearchService
to avoid duplicated summary-fetching logic.
"""

import kuzu


def get_article_summaries(
    conn: kuzu.Connection,
    titles: list[str],
) -> dict[str, str]:
    """
    Fetch the first section content for each article as a summary.

    Uses a single batch query to retrieve summaries for all titles,
    avoiding the N+1 query problem.

    Args:
        conn: Kuzu database connection
        titles: List of article titles to fetch summaries for

    Returns:
        Dict mapping article title to its summary string.
        Articles with no content are omitted from the result.
    """
    if not titles:
        return {}

    result = conn.execute(
        """
        MATCH (a:Article)-[:HAS_SECTION]->(s:Section)
        WHERE a.title IN $titles
        RETURN a.title AS title, s.content AS content, s.section_id AS sid
        ORDER BY title, sid ASC
        """,
        {"titles": titles},
    )

    summaries: dict[str, str] = {}
    for _, row in result.get_as_df().iterrows():
        title = row["title"]
        if title not in summaries:
            content = row["content"]
            if content:
                summaries[title] = content[:200] + "..." if len(content) > 200 else content

    return summaries
