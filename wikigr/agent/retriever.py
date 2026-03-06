"""Retrieval functions extracted from KnowledgeGraphAgent.

All functions take explicit parameters instead of ``self``, enabling
independent testing and reuse.  The parent ``KnowledgeGraphAgent`` class
wraps each function so that its public (and private) method API is
unchanged.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import APIConnectionError, APIStatusError, APITimeoutError

from wikigr.agent.kg_agent import _QUESTION_PREFIX_RE, _strip_markdown_fences

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: safe query execution
# ---------------------------------------------------------------------------


def _safe_query(conn, cypher: str, params: dict | None = None, *, log_context: str = "") -> Any:
    """Execute Cypher and return DataFrame, or None on failure."""
    try:
        result = conn.execute(cypher, params or {})
        df = result.get_as_df()
        return df if not df.empty else None
    except RuntimeError as e:
        logger.debug("Query failed%s: %s", f" ({log_context})" if log_context else "", e)
        return None


# ---------------------------------------------------------------------------
# Direct title lookup
# ---------------------------------------------------------------------------


def direct_title_lookup(conn, question: str) -> list[str]:
    """Phase 2: Direct article title matching for better retrieval.

    Extracts key noun phrases from the question and looks up articles
    with matching titles. This catches cases where the LLM query planner
    generates bad Cypher but the answer is in an obviously-named article.
    """
    cleaned = _QUESTION_PREFIX_RE.sub("", question.lower()).rstrip("?. ")

    candidates = []
    # Exact match (case-insensitive)
    df = _safe_query(
        conn,
        "MATCH (a:Article) WHERE lower(a.title) = $q RETURN a.title",
        {"q": cleaned},
        log_context="direct title exact match",
    )
    if df is not None:
        candidates.extend(df["a.title"].tolist())

    # Partial match if no exact match
    if not candidates:
        df = _safe_query(
            conn,
            "MATCH (a:Article) WHERE lower(a.title) CONTAINS $q "
            "RETURN a.title ORDER BY length(a.title) ASC LIMIT 3",
            {"q": cleaned},
            log_context="direct title partial match",
        )
        if df is not None:
            candidates.extend(df["a.title"].tolist())

    return candidates[:3]


# ---------------------------------------------------------------------------
# Multi-query retrieval
# ---------------------------------------------------------------------------


def multi_query_retrieve(
    claude_client,
    semantic_search_fn,
    track_response_fn,
    question: str,
    max_results: int = 5,
) -> list[dict]:
    """Retrieve results using original question plus 2 alternative phrasings.

    Generates 2 alternative phrasings via Claude Haiku, runs semantic_search
    for all 3 queries, then deduplicates by title keeping the highest similarity
    score, and returns results sorted descending by similarity.

    Args:
        claude_client: Anthropic client instance.
        semantic_search_fn: Callable that performs semantic search (query, top_k) -> list[dict].
        track_response_fn: Callable to track token usage from API responses.
        question: Original natural language question.
        max_results: Maximum results per query (deduplication reduces final count).

    Returns:
        Deduplicated list of result dicts sorted by similarity descending.
    """
    max_results = max(1, min(max_results, 20))

    question_truncated = question[:500]
    alternatives: list[str] = []
    try:
        expansion_response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            timeout=10.0,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Generate exactly 2 alternative phrasings of this question for semantic search. "
                        f"Return a JSON array of 2 strings and nothing else.\n\nQuestion: {question_truncated}"
                    ),
                }
            ],
        )
        track_response_fn(expansion_response)
        raw = _strip_markdown_fences(
            expansion_response.content[0].text.strip() if expansion_response.content else "[]"
        )
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            alternatives = [str(p)[:300] for p in parsed[:2]]
    except APITimeoutError:
        logger.warning("Multi-query expansion timed out; falling back to original query")
    except APIConnectionError as e:
        logger.warning(
            f"Multi-query expansion connection error: {e}; falling back to original query"
        )
    except APIStatusError as e:
        if e.status_code == 429:
            logger.warning("Multi-query expansion rate-limited; falling back to original query")
        else:
            logger.warning(
                f"Multi-query expansion API error (status={e.status_code}); falling back to original query"
            )
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Multi-query expansion returned invalid JSON: {e}")

    all_queries = [question] + alternatives
    merged: dict[str, dict] = {}

    for query in all_queries:
        try:
            results = semantic_search_fn(query, top_k=max_results)
            for result in results:
                title = result.get("title", "")
                if not title:
                    continue
                existing = merged.get(title)
                if existing is None or result.get("similarity", 0.0) > existing.get(
                    "similarity", 0.0
                ):
                    merged[title] = result
        except (RuntimeError, OSError) as e:
            logger.warning(
                f"Multi-query search failed for query '{query[:100]}{'...' if len(query) > 100 else ''}': {e}"
            )

    return sorted(merged.values(), key=lambda r: r.get("similarity", 0.0), reverse=True)


# ---------------------------------------------------------------------------
# Vector-primary retrieval
# ---------------------------------------------------------------------------


def vector_primary_retrieve(
    semantic_search_fn,
    multi_query_retrieve_fn,
    cross_encoder,
    enable_multi_query: bool,
    question: str,
    max_results: int,
) -> tuple[dict | None, float]:
    """Attempt vector search as primary retrieval.

    Args:
        semantic_search_fn: Callable (query, top_k) -> list[dict].
        multi_query_retrieve_fn: Callable (question, max_results) -> list[dict].
        cross_encoder: Cross-encoder reranker or None.
        enable_multi_query: Whether multi-query expansion is enabled.
        question: Natural language question.
        max_results: Maximum results to return.

    Returns:
        (kg_results_dict, max_similarity) or (None, 0.0) on failure.
    """
    try:
        candidate_k = min(max_results * 2, 40) if cross_encoder is not None else max_results
        if enable_multi_query:
            vector_results = multi_query_retrieve_fn(question, max_results=candidate_k)
        else:
            vector_results = semantic_search_fn(question, top_k=candidate_k)
        if not vector_results:
            return None, 0.0

        if cross_encoder is not None:
            vector_results = cross_encoder.rerank(question, vector_results, top_k=max_results)

        max_similarity = 0.0
        sources = []
        facts = []
        for r in vector_results:
            sim = r.get("similarity", 0.0)
            if sim > max_similarity:
                max_similarity = sim
            title = r["title"]
            sources.append(title)
            content = r.get("content", "")
            if content:
                facts.append(f"[{title}] {content[:500]}")
        return {
            "sources": sources,
            "entities": [],
            "facts": facts,
            "raw": [
                {"title": r["title"], "score": r.get("similarity", 0.0)} for r in vector_results
            ],
        }, max_similarity
    except (RuntimeError, OSError) as e:
        logger.warning(f"Vector primary retrieve failed: {e}")
        return None, 0.0


# ---------------------------------------------------------------------------
# Hybrid retrieval
# ---------------------------------------------------------------------------


def hybrid_retrieve(
    conn,
    semantic_search_fn,
    stop_words: frozenset[str],
    question: str,
    max_results: int = 10,
    vector_weight: float = 0.5,
    graph_weight: float = 0.3,
    keyword_weight: float = 0.2,
    _precomputed_vector: list[dict] | None = None,
) -> dict[str, Any]:
    """Combine vector, graph, and keyword retrieval for richer results.

    Args:
        conn: Database connection.
        semantic_search_fn: Callable (query, top_k) -> list[dict].
        stop_words: Set of stop words for keyword filtering.
        question: Natural language question.
        max_results: Maximum articles to return.
        vector_weight: Weight for vector similarity signal (0-1).
        graph_weight: Weight for graph proximity signal (0-1).
        keyword_weight: Weight for keyword match signal (0-1).
        _precomputed_vector: Pre-computed semantic_search results to avoid a
            duplicate DB call when the caller already ran vector retrieval.

    Returns:
        KG results dict with sources, entities, facts, raw.
    """
    scored: dict[str, float] = {}

    # Signal 1: Vector search
    if _precomputed_vector is not None:
        vector_results = _precomputed_vector
    else:
        try:
            vector_results = semantic_search_fn(question, top_k=max_results)
        except (RuntimeError, OSError) as e:
            logger.warning(f"Vector search failed in hybrid retrieve: {e}")
            vector_results = []
    for r in vector_results:
        title = r.get("article", r.get("title", ""))
        if title:
            scored[title] = scored.get(title, 0) + vector_weight * r.get("similarity", 0.5)

    # Signal 2: Graph traversal
    seed_titles = list(scored.keys())[:3]
    for seed in seed_titles:
        df = _safe_query(
            conn,
            "MATCH (seed:Article {title: $title})-[:LINKS_TO]->(neighbor:Article) "
            "RETURN neighbor.title AS title LIMIT $limit",
            {"title": seed, "limit": max_results},
            log_context=f"hybrid graph traversal for '{seed}'",
        )
        if df is not None:
            for title in df["title"].tolist():
                if title:
                    scored[title] = scored.get(title, 0) + graph_weight * 0.5

    # Signal 3: Keyword match
    keywords = [w for w in question.split() if len(w) > 3 and w.lower() not in stop_words]
    for kw in keywords[:3]:
        df = _safe_query(
            conn,
            "MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($kw) "
            "RETURN a.title AS title LIMIT $limit",
            {"kw": kw, "limit": max_results},
            log_context=f"hybrid keyword search for '{kw}'",
        )
        if df is not None:
            for title in df["title"].tolist():
                if title:
                    scored[title] = scored.get(title, 0) + keyword_weight * 0.7

    ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:max_results]
    source_titles = [title for title, _score in ranked]

    # Fetch facts for top sources
    facts: list[str] = []
    if source_titles:
        df = _safe_query(
            conn,
            "MATCH (a:Article)-[:HAS_FACT]->(f:Fact) "
            "WHERE a.title IN $titles "
            "RETURN f.content AS content LIMIT 15",
            {"titles": source_titles[:5]},
            log_context="hybrid facts batch",
        )
        if df is not None and "content" in df.columns:
            facts = df["content"].dropna().tolist()

    return {
        "sources": source_titles,
        "entities": [],
        "facts": facts,
        "raw": [{"title": t, "score": s} for t, s in ranked[:10]],
    }


# ---------------------------------------------------------------------------
# Section quality scoring
# ---------------------------------------------------------------------------


def score_section_quality(
    content: str,
    question: str,
    stop_words: frozenset[str],
    *,
    _q_keywords: frozenset[str] | None = None,
) -> float:
    """Score a section's quality for inclusion in synthesis context.

    Args:
        content: Section text content.
        question: User question (used for keyword overlap scoring).
        stop_words: Set of stop words to exclude from keyword overlap.
        _q_keywords: Pre-computed question keywords (frozenset). When
            supplied by the caller, this avoids re-splitting and
            re-filtering the question on every invocation.

    Returns:
        Quality score in [0.0, 1.0]. Returns 0.0 for stubs under 20 words.
    """
    words = content.split()
    word_count = len(words)
    if word_count < 20:
        return 0.0

    length_score = min(0.8, 0.2 + (word_count / 200) * 0.6)

    question_keywords = (
        _q_keywords
        if _q_keywords is not None
        else frozenset(lw for w in question.split() if (lw := w.lower()) not in stop_words)
    )
    if question_keywords:
        content_words_lower = {w.lower() for w in words}
        overlap = len(question_keywords & content_words_lower) / len(question_keywords)
        keyword_score = overlap * 0.2
    else:
        keyword_score = 0.0

    return min(1.0, length_score + keyword_score)


# ---------------------------------------------------------------------------
# Fetch source text
# ---------------------------------------------------------------------------


def fetch_source_text(
    conn,
    score_section_quality_fn,
    stop_words: frozenset[str],
    max_article_chars: int,
    content_quality_threshold: float,
    source_titles: list[str],
    max_articles: int = 5,
    question: str | None = None,
) -> str:
    """Fetch section text for source articles (batched, single query).

    Retrieves ALL section content for each source article, concatenated,
    providing Claude with rich source text for grounded synthesis.
    Falls back to article-level content if sections aren't available.

    When ``question`` is provided, sections below content_quality_threshold
    are filtered out before inclusion.
    """
    titles = source_titles[:max_articles]
    if not titles:
        return ""

    texts: list[str] = []

    df = _safe_query(
        conn,
        "MATCH (a:Article)-[:HAS_SECTION]->(s:Section) "
        "WHERE a.title IN $titles "
        "RETURN a.title AS title, s.content AS content "
        "ORDER BY a.title",
        {"titles": titles},
        log_context="fetch source sections",
    )
    if df is not None:
        from wikigr.packs.content_cleaner import clean_content

        q_keywords: frozenset[str] | None = None
        if question is not None:
            q_keywords = frozenset(
                lw for w in question.split() if (lw := w.lower()) not in stop_words
            )

        by_article: dict[str, list[str]] = {}
        for title, sect_content in zip(df["title"].tolist(), df["content"].tolist()):
            if title and sect_content:
                cleaned = clean_content(sect_content)
                if q_keywords is not None and (
                    score_section_quality_fn(cleaned, question, _q_keywords=q_keywords)
                    < content_quality_threshold
                ):
                    continue
                by_article.setdefault(title, []).append(cleaned)

        for title in titles:
            sections = by_article.get(title, [])
            if sections:
                combined = "\n\n".join(sections)
                truncated = combined[:max_article_chars] + (
                    "..." if len(combined) > max_article_chars else ""
                )
                texts.append(f"## {title}\n{truncated}")

    # Fallback: try article.content directly if no sections found
    if not texts:
        df = _safe_query(
            conn,
            "MATCH (a:Article) WHERE a.title IN $titles "
            "RETURN a.title AS title, a.content AS content",
            {"titles": titles},
            log_context="fetch source article content fallback",
        )
        if df is not None:
            for title, content in zip(df["title"].tolist(), df["content"].tolist()):
                if title and content:
                    truncated = content[:max_article_chars] + (
                        "..." if len(content) > max_article_chars else ""
                    )
                    texts.append(f"## {title}\n{truncated}")

    return "\n\n".join(texts)
