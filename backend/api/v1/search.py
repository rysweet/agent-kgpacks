"""
Search API endpoints.

Provides semantic search and autocomplete functionality.
"""

import logging
from datetime import datetime, timezone

import kuzu
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.db import get_db
from backend.models.common import ErrorResponse
from backend.models.search import AutocompleteResponse, SearchResponse
from backend.rate_limit import limiter
from backend.services import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["search"])


@router.get(
    "/search",
    response_model=SearchResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
@limiter.limit("10/minute")
def search(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    response: Response,
    query: str = Query(..., max_length=200, description="Search query (article title)"),
    category: str | None = Query(None, max_length=200, description="Optional category filter"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    threshold: float = Query(0.0, ge=0.0, le=1.0, description="Minimum similarity threshold"),
    conn: kuzu.Connection = Depends(get_db),
):
    """
    Perform semantic search for similar articles.

    Finds articles semantically similar to the query article.
    """
    # Set cache headers
    response.headers["Cache-Control"] = "private, max-age=3600"

    try:
        result = SearchService.semantic_search(
            conn=conn,
            query=query,
            category=category,
            limit=limit,
            threshold=threshold,
        )
        return result

    except ValueError as e:
        logger.warning(f"Search query error: {e}")
        error_msg = str(e)

        if "not found" in error_msg.lower():
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": error_msg,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "INVALID_PARAMETER",
                        "message": error_msg,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

    except Exception as e:
        logger.error(f"Unexpected error in search endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.get(
    "/autocomplete",
    response_model=AutocompleteResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
@limiter.limit("60/minute")
def autocomplete(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    response: Response,
    q: str = Query(
        ..., min_length=2, max_length=200, description="Query string (minimum 2 characters)"
    ),
    limit: int = Query(10, ge=1, le=20, description="Maximum suggestions"),
    conn: kuzu.Connection = Depends(get_db),
):
    """
    Get autocomplete suggestions for article titles.

    Returns articles with titles matching the query.
    """
    # Set cache headers
    response.headers["Cache-Control"] = "private, max-age=3600"

    try:
        result = SearchService.autocomplete(
            conn=conn,
            q=q,
            limit=limit,
        )
        return result

    except ValueError as e:
        logger.warning(f"Autocomplete query error: {e}")
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "INVALID_PARAMETER",
                    "message": str(e),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Unexpected error in autocomplete endpoint: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
