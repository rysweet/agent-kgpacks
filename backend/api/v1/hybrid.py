"""
Hybrid search API endpoint.

Combines semantic similarity with graph proximity for richer search results.
"""

import logging
from datetime import datetime, timezone

import kuzu
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.db import get_db
from backend.models.common import ErrorResponse
from backend.models.search import SearchResponse, SearchResult
from backend.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get(
    "/hybrid-search",
    response_model=SearchResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
@limiter.limit("10/minute")
def hybrid_search(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    response: Response,
    query: str = Query(..., max_length=200, description="Seed article title"),
    category: str | None = Query(None, max_length=200, description="Category filter"),
    max_hops: int = Query(2, ge=1, le=3, description="Max graph hops"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    conn: kuzu.Connection = Depends(get_db),
):
    """
    Hybrid search combining semantic similarity (70%) and graph proximity (30%).

    Returns articles ranked by a weighted combination of vector similarity
    and link-graph distance from the seed article.
    """
    import time

    response.headers["Cache-Control"] = "public, max-age=3600"
    start = time.perf_counter()

    try:
        from bootstrap.src.query.search import hybrid_query

        results = hybrid_query(
            conn=conn,
            seed_title=query,
            category=category,
            max_hops=max_hops,
            top_k=limit,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        search_results = [
            SearchResult(
                title=r["article_title"],
                similarity=r.get("combined_score", r.get("similarity", 0.0)),
                category=r.get("category", ""),
            )
            for r in results
        ]

        return SearchResponse(
            query=query,
            results=search_results,
            total=len(search_results),
            execution_time_ms=round(elapsed_ms, 1),
        )

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return JSONResponse(
                status_code=404,
                content={
                    "error": {"code": "NOT_FOUND", "message": "Article not found"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        return JSONResponse(
            status_code=400,
            content={
                "error": {"code": "INVALID_PARAMETER", "message": error_msg},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Hybrid search error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
