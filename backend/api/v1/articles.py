"""
Articles API endpoints.

Provides article details, categories, and statistics.
"""

import logging
from datetime import datetime, timezone

import kuzu
from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.db import get_db
from backend.models.article import ArticleDetail, CategoryListResponse, StatsResponse
from backend.models.common import ErrorResponse
from backend.rate_limit import limiter
from backend.services import ArticleService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["articles"])


@router.get(
    "/articles/{title}",
    response_model=ArticleDetail,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
@limiter.limit("30/minute")
async def get_article(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    response: Response,
    title: str = Path(..., max_length=500, description="Article title (URL-encoded)"),
    conn: kuzu.Connection = Depends(get_db),
):
    """
    Get detailed information about a specific article.

    Returns article metadata, sections, links, and backlinks.
    """
    # Set cache headers
    response.headers["Cache-Control"] = "public, max-age=86400"

    try:
        result = ArticleService.get_article_details(conn=conn, title=title)
        return result

    except ValueError as e:
        logger.warning(f"Article not found: {e}")
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(e),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Unexpected error in article endpoint: {e}", exc_info=True)
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
    "/categories",
    response_model=CategoryListResponse,
    responses={500: {"model": ErrorResponse}},
)
@limiter.limit("30/minute")
async def get_categories(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    response: Response,
    conn: kuzu.Connection = Depends(get_db),
):
    """
    Get list of all categories with article counts.

    Returns categories sorted by article count (descending).
    """
    # Set cache headers
    response.headers["Cache-Control"] = "public, max-age=3600"

    try:
        result = ArticleService.get_categories(conn=conn)
        return result

    except Exception as e:
        logger.error(f"Unexpected error in categories endpoint: {e}", exc_info=True)
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
    "/stats",
    response_model=StatsResponse,
    responses={500: {"model": ErrorResponse}},
)
@limiter.limit("30/minute")
async def get_stats(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    response: Response,
    conn: kuzu.Connection = Depends(get_db),
):
    """
    Get database statistics and metrics.

    Returns comprehensive statistics about articles, sections, links, and performance.
    """
    # Set cache headers
    response.headers["Cache-Control"] = "public, max-age=300"

    try:
        result = ArticleService.get_stats(conn=conn, db_path=settings.database_path)
        return result

    except Exception as e:
        logger.error(f"Unexpected error in stats endpoint: {e}", exc_info=True)
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
