"""OpenAI-compatible API surface.

Implements a subset of the OpenAI REST API so existing OpenAI client libraries
and tools can talk to this app:

    GET  /v1/models
    POST /v1/chat/completions   (streaming and non-streaming)

Requests are routed to the app's configured LLM provider (Ollama / Anthropic /
OpenAI). Authentication uses the app's own API keys (``Authorization: Bearer
<rak_...>``), consistent with the rest of the REST API.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.base import get_session
from app.llm.factory import get_provider
from app.observability.logging import get_logger
from app.settings import get_settings

router = APIRouter()
log = get_logger(__name__)


class ChatMessageIn(BaseModel):
    role: str
    content: Any = None


class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessageIn]
    model: str | None = None
    stream: bool = False
    temperature: float = 0.7


def _flatten(content: Any) -> str:
    """Coerce OpenAI message content (str or list-of-parts) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(p.get("text", ""))
            else:
                parts.append(str(p))
        return "".join(parts)
    return str(content)


def _require_key(request: Request) -> str | None:
    """Return the tenant id for the request's API key (or None in open mode)."""
    s = get_settings()
    auth = request.headers.get("Authorization", "")
    raw = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    raw = raw or request.headers.get("X-API-Key")

    if not s.require_api_key:
        return "open"
    if not raw:
        return None
    session: Session = get_session()
    try:
        tenant = repo.authenticate(session, raw)
        session.commit()
    finally:
        session.close()
    return tenant.id if tenant else None


def _split_messages(messages: list[ChatMessageIn]) -> tuple[str, list[dict]]:
    """Separate system text from the user/assistant turn list."""
    system_parts: list[str] = []
    turns: list[dict] = []
    for m in messages:
        text = _flatten(m.content)
        if m.role == "system":
            system_parts.append(text)
        elif m.role in ("user", "assistant"):
            turns.append({"role": m.role, "content": text})
    return "\n\n".join(system_parts), turns


@router.get("/v1/models")
async def list_models(request: Request):
    tenant = _require_key(request)
    if tenant is None:
        return JSONResponse({"error": "Invalid or missing API key"}, status_code=401)
    s = get_settings()
    model_id = s.active_model()
    return {
        "object": "list",
        "data": [
            {
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": s.llm_provider,
            }
        ],
    }


@router.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    tenant = _require_key(request)
    if tenant is None:
        return JSONResponse({"error": "Invalid or missing API key"}, status_code=401)
    if not body.messages:
        return JSONResponse({"error": "messages is required"}, status_code=422)

    system, turns = _split_messages(body.messages)
    if not turns:
        return JSONResponse(
            {"error": "at least one user/assistant message is required"},
            status_code=422,
        )

    provider = get_provider(model=body.model)
    model_name = provider.model
    completion_id = "chatcmpl-" + uuid.uuid4().hex
    created = int(time.time())

    if body.stream:
        def event_stream():
            # Opening chunk advertises the assistant role.
            yield _sse_chunk(completion_id, created, model_name, role="assistant")
            try:
                for piece in provider.stream_chat(
                    system, turns, temperature=body.temperature
                ):
                    yield _sse_chunk(completion_id, created, model_name, content=piece)
            except Exception as exc:  # noqa: BLE001 - surface as a final chunk
                log.error("openai_compat.stream_failed", error=str(exc))
            yield _sse_chunk(
                completion_id, created, model_name, finish_reason="stop"
            )
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_stream(), media_type="text/event-stream"
        )

    # Non-streaming: accumulate the full reply.
    try:
        text = "".join(
            provider.stream_chat(system, turns, temperature=body.temperature)
        ).strip()
    except Exception as exc:  # noqa: BLE001
        log.error("openai_compat.failed", error=str(exc))
        return JSONResponse(
            {"error": f"upstream model error: {exc}"}, status_code=502
        )

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


def _sse_chunk(
    completion_id: str,
    created: int,
    model: str,
    *,
    role: str | None = None,
    content: str | None = None,
    finish_reason: str | None = None,
) -> str:
    delta: dict = {}
    if role is not None:
        delta["role"] = role
    if content is not None:
        delta["content"] = content
    chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(chunk)}\n\n"
