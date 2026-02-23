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


@router.get("/chat/stream")
@limiter.limit("5/minute")
def chat_stream(
    request: Request,  # noqa: ARG001 - required by slowapi limiter
    question: str = Query(..., max_length=500),
    max_results: int = Query(10, ge=1, le=50),
    conn: kuzu.Connection = Depends(get_db),
):
    """
    Stream a chat response via Server-Sent Events.

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
        try:
            from wikigr.agent.kg_agent import KnowledgeGraphAgent

            agent = KnowledgeGraphAgent.__new__(KnowledgeGraphAgent)
            agent.db = None
            agent.conn = conn
            agent.claude = _get_anthropic_client()
            agent._embedding_generator = None
            agent._plan_cache = {}

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
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
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

    return EventSourceResponse(generate())
