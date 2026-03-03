"""
Chat API endpoint.

Wraps KnowledgeGraphAgent for browser-based Q&A against the knowledge graph.
Uses the shared ConnectionManager (via get_db dependency) instead of opening
a separate database per request. Supports both blocking and streaming responses.
"""

import concurrent.futures
import contextlib
import json
import logging
import os
import time
from pathlib import Path

import kuzu
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from backend.config import settings
from backend.db import get_connection, get_db
from backend.models.chat import ChatRequest, ChatResponse
from backend.rate_limit import limiter
from wikigr.packs.manifest import PACK_NAME_RE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Module-level Anthropic client (created once, reused across requests)
_anthropic_client = None

# Maximum seconds to wait for agent.query() before emitting a timeout error (R-DOS-1)
STREAM_TIMEOUT_S = int(os.environ.get("WIKIGR_STREAM_TIMEOUT_S", "60"))


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
@limiter.limit(settings.chat_rate_limit)
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

        pack_agent = None
        if request_body.pack:
            # Validate pack name to prevent path traversal
            if not PACK_NAME_RE.match(request_body.pack):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {"code": "INVALID_PACK_NAME", "message": "Invalid pack name"}
                    },
                )
            packs_base = Path(settings.database_path).resolve().parent / "packs"
            pack_db_path = (packs_base / request_body.pack / "pack.db").resolve()
            if not pack_db_path.is_relative_to(packs_base):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {"code": "INVALID_PACK_NAME", "message": "Invalid pack name"}
                    },
                )
            pack_db = str(pack_db_path)
            if not os.path.exists(pack_db):
                return JSONResponse(
                    status_code=404,
                    content={
                        "error": {
                            "code": "PACK_NOT_FOUND",
                            "message": "Requested pack was not found",
                        }
                    },
                )
            pack_agent = KnowledgeGraphAgent(pack_db, read_only=True)
            agent = pack_agent
        else:
            # Use the shared connection (default database)
            agent = KnowledgeGraphAgent.from_connection(conn, _get_anthropic_client())

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
                    "message": "Agent encountered an error",
                }
            },
        )
    finally:
        if pack_agent is not None:
            pack_agent.close()


@router.get("/chat/stream")
@limiter.limit(settings.chat_rate_limit)
def chat_stream(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    question: str = Query(..., min_length=1, max_length=500),
    max_results: int = Query(10, ge=1, le=50),
):
    """
    Stream a chat response via Server-Sent Events.

    Note: This endpoint manages its own database connection inside the
    generator to ensure the connection stays alive for the full duration
    of the SSE stream (not closed early by FastAPI's dependency lifecycle).

    Events:
    - type=token: incremental answer text
    - type=sources: JSON array of source article titles
    - type=done: final metadata (query_type, execution_time_ms)
    - type=error: error message
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse(status_code=503, content={"error": {"code": "AGENT_UNAVAILABLE"}})

    def generate():
        start = time.perf_counter()
        # Manage connection inside generator so it stays alive for the full stream
        conn = get_connection()
        try:
            from wikigr.agent.kg_agent import KnowledgeGraphAgent

            agent = KnowledgeGraphAgent.from_connection(conn, _get_anthropic_client())

            # Run agent.query with a timeout to bound SSE connection lifetime (R-DOS-1)
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = pool.submit(agent.query, question=question, max_results=max_results)
            try:
                result = future.result(timeout=STREAM_TIMEOUT_S)
            except concurrent.futures.TimeoutError:
                pool.shutdown(wait=False, cancel_futures=True)
                # Intentionally "TimeoutError" (not "AgentError") so clients can
                # distinguish a deadline-exceeded condition from a generic agent fault
                # and apply appropriate retry / back-off logic.
                yield {"event": "error", "data": "TimeoutError"}
                return
            else:
                pool.shutdown(wait=False)

            yield {"event": "sources", "data": json.dumps(result.get("sources", []))}
            yield {"event": "token", "data": result.get("answer", "")}

            elapsed_ms = (time.perf_counter() - start) * 1000
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "query_type": result.get("query_type", "unknown"),
                        "execution_time_ms": round(elapsed_ms, 1),
                    }
                ),
            }

        except Exception as e:
            logger.error(f"Streaming chat error: {e}", exc_info=True)
            yield {"event": "error", "data": "AgentError"}
        finally:
            with contextlib.suppress(Exception):
                conn.close()

    return EventSourceResponse(generate())
