"""
Graph API endpoints.

Provides endpoints for graph traversal and visualization data.
"""

import logging
from datetime import datetime, timezone

import kuzu
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.db import get_db
from backend.models.common import ErrorResponse
from backend.models.graph import GraphResponse
from backend.rate_limit import limiter
from backend.services import GraphService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["graph"])


@router.get(
    "/graph",
    response_model=GraphResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
@limiter.limit("20/minute")
def get_graph(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    response: Response,
    article: str = Query(..., max_length=500, description="Seed article title"),
    depth: int = Query(2, ge=1, le=3, description="Maximum depth to traverse"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of nodes"),
    category: str | None = Query(None, max_length=200, description="Optional category filter"),
    conn: kuzu.Connection = Depends(get_db),
):
    """
    Get graph structure around seed article.

    Returns nodes and edges within specified depth from seed article.
    """
    # Set cache headers
    response.headers["Cache-Control"] = "public, max-age=3600"

    try:
        result = GraphService.get_graph_neighbors(
            conn=conn,
            article=article,
            depth=depth,
            limit=limit,
            category=category,
        )
        return result

    except ValueError as e:
        logger.warning(f"Graph query error: {e}")
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
        logger.error(f"Unexpected error in graph endpoint: {e}", exc_info=True)
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
