"""
Chat API endpoint.

Wraps KnowledgeGraphAgent for browser-based Q&A against the knowledge graph.
"""

import logging
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.models.chat import ChatRequest, ChatResponse
from backend.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        503: {"description": "Agent unavailable (missing API key or DB)"},
    },
)
@limiter.limit("5/minute")
def chat(
    request_body: ChatRequest,
    request: Request,  # noqa: ARG001 - required by slowapi limiter
) -> ChatResponse | JSONResponse:
    """
    Ask a question about the knowledge graph.

    Creates a fresh KnowledgeGraphAgent per request, queries the graph,
    and returns a synthesized answer with source citations.

    Returns HTTP 503 when ANTHROPIC_API_KEY is not configured.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("Chat request rejected: ANTHROPIC_API_KEY not set")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "AGENT_UNAVAILABLE",
                    "message": "Chat agent is not available. ANTHROPIC_API_KEY is not configured.",
                }
            },
        )

    db_path = settings.database_path
    if not db_path:
        logger.error("Chat request rejected: no database path configured")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Knowledge graph database is not configured.",
                }
            },
        )

    start = time.perf_counter()
    agent = None

    try:
        from wikigr.agent.kg_agent import KnowledgeGraphAgent

        agent = KnowledgeGraphAgent(
            db_path=db_path,
            anthropic_api_key=api_key,
            read_only=True,
        )

        result = agent.query(
            question=request_body.question,
            max_results=request_body.max_results,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        return ChatResponse(
            answer=result.get("answer", "No answer generated."),
            sources=result.get("sources", []),
            query_type=result.get("query_type", "unknown"),
            execution_time_ms=round(elapsed_ms, 1),
        )

    except FileNotFoundError:
        logger.error(f"Database not found at {db_path}")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Knowledge graph database not found at configured path.",
                }
            },
        )

    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.error(f"Chat agent error after {elapsed_ms:.0f}ms: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "AGENT_ERROR",
                    "message": f"Agent encountered an error: {type(e).__name__}",
                }
            },
        )

    finally:
        if agent is not None:
            try:
                agent.close()
            except Exception as close_err:
                logger.debug(f"Agent close error (non-fatal): {close_err}")
