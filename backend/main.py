"""
WikiGR Visualization API.

FastAPI application providing RESTful API for Wikipedia knowledge graph queries.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import kuzu
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.v1 import articles, graph, search
from backend.config import settings
from backend.db import get_db
from backend.models.common import HealthResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    logger.info(f"Starting {settings.api_title} v{settings.api_version}")
    logger.info(f"Database: {settings.database_path}")
    logger.info(f"CORS origins: {settings.cors_origins}")
    yield
    logger.info("Shutting down WikiGR Visualization API")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(graph.router)
app.include_router(search.router)
app.include_router(articles.router)


@app.get("/health", response_model=HealthResponse)
async def health_check(
    response: Response,
    conn: kuzu.Connection = Depends(get_db),
):
    """
    Health check endpoint.

    Returns service status and database connectivity.
    """
    # Set no-cache headers
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    try:
        # Test database connection
        result = conn.execute("RETURN 1 AS test")
        result.has_next()

        db_status = "connected"
        status = "healthy"

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_status = "disconnected"
        status = "unhealthy"

    return HealthResponse(
        status=status,
        version=settings.api_version,
        database=db_status,
        timestamp=datetime.now(timezone.utc),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    """
    Handle validation errors and return 400 instead of 422.
    """
    logger.warning(f"Validation error: {exc}")

    # Extract missing field information
    errors = exc.errors()
    error_msg = "Invalid parameters"

    if errors:
        first_error = errors[0]
        if first_error.get("type") == "missing":
            field = first_error.get("loc", [])[-1]
            error_msg = f"Missing required parameter: {field}"
            code = "MISSING_PARAMETER"
        else:
            error_msg = first_error.get("msg", "Invalid parameters")
            code = "INVALID_PARAMETER"
    else:
        code = "INVALID_PARAMETER"

    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": code,
                "message": error_msg,
            },
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(_request, exc):
    """
    Global exception handler for unhandled errors.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
            },
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level="info",
    )
