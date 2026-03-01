"""
Chat API endpoint.

Wraps KnowledgeGraphAgent for browser-based Q&A against the knowledge graph.
Uses the shared ConnectionManager (via get_db dependency) instead of opening
a separate database per request. Supports both blocking and streaming responses.
"""

import json
import logging
import os
import time

import kuzu
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from backend.config import settings
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
            # Open a specific pack by name
            pack_db = os.path.join("data", "packs", request_body.pack, "pack.db")
            if not os.path.exists(pack_db):
                return JSONResponse(
                    status_code=404,
                    content={"error": {"code": "PACK_NOT_FOUND", "message": f"Pack '{request_body.pack}' not found"}},
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
                    "message": f"Agent encountered an error: {type(e).__name__}",
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
    question: str = Query(..., max_length=500),
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
        from backend.db.connection import _manager

        conn = _manager.get_connection()
        try:
            from wikigr.agent.kg_agent import KnowledgeGraphAgent

            agent = KnowledgeGraphAgent.from_connection(conn, _get_anthropic_client())

            # Step 1: Plan query (fast)
            query_plan = agent._plan_query(question)

            # Step 2: Execute query (fast)
            kg_results = agent._execute_query(
                query_plan["cypher"], max_results, query_plan.get("cypher_params")
            )

            # Send sources immediately
            sources = kg_results.get("sources", [])
            yield {"event": "sources", "data": json.dumps(sources)}

            # Step 3: Stream synthesis from Claude
            context = agent._build_synthesis_context(question, kg_results, query_plan)
            client = agent.claude

            with client.messages.stream(
                model=agent.synthesis_model,
                max_tokens=agent.SYNTHESIS_MAX_TOKENS,
                messages=[{"role": "user", "content": context}],
            ) as stream:
                for text in stream.text_stream:
                    yield {"event": "token", "data": text}

            elapsed_ms = (time.perf_counter() - start) * 1000
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "query_type": query_plan.get("type", "unknown"),
                        "execution_time_ms": round(elapsed_ms, 1),
                    }
                ),
            }

        except Exception as e:
            logger.error(f"Streaming chat error: {e}", exc_info=True)
            yield {"event": "error", "data": str(type(e).__name__)}
        finally:
            import contextlib

            with contextlib.suppress(Exception):
                conn.close()

    return EventSourceResponse(generate())
