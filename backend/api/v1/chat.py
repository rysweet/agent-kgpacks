"""
Chat API endpoint.

Wraps KnowledgeGraphAgent for browser-based Q&A against the knowledge graph.
Uses the shared ConnectionManager (via get_db dependency) instead of opening
a separate database per request.
"""

import logging
import os
import time

import kuzu
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from backend.db import get_db
from backend.models.chat import ChatRequest, ChatResponse
from backend.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Module-level Anthropic client (created once, reused across requests)
_anthropic_client = None


def _get_anthropic_client():
    """Get or create a shared Anthropic client."""
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic

        _anthropic_client = Anthropic()
    return _anthropic_client


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
    conn: kuzu.Connection = Depends(get_db),
) -> ChatResponse | JSONResponse:
    """
    Ask a question about the knowledge graph.

    Uses the shared database connection pool and a module-level Anthropic client
    to avoid per-request overhead of opening DB and creating API clients.

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

    start = time.perf_counter()

    try:
        from wikigr.agent.kg_agent import KnowledgeGraphAgent

        # Create agent with injected connection (no DB open overhead)
        agent = KnowledgeGraphAgent.__new__(KnowledgeGraphAgent)
        agent.db = None  # Not managing DB lifecycle
        agent.conn = conn
        agent.claude = _get_anthropic_client()
        agent._embedding_generator = None

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
