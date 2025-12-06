from __future__ import annotations

import json
import time
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..engine import CompletionResult, MiniMediatorEngine
from ..providers.utils import apply_chunk_delay


def build_router(engine: MiniMediatorEngine) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["openai"])

    @router.get("/models")
    async def list_models() -> JSONResponse:
        return JSONResponse(engine.list_models())

    @router.post("/chat/completions")
    async def chat_completions(request: Request):
        payload = await request.json()
        stream = payload.get("stream", False)
        stream_options = payload.get("stream_options") or {}
        include_usage = bool(stream_options.get("include_usage"))
        result = engine.chat_completion(payload)
        if result.error:
            raise HTTPException(
                status_code=result.error.status_code,
                detail=result.error.body.get("error"),
                headers=result.error.headers,
            )
        if stream and result.chunk_plan:
            generator = _openai_stream(
                result,
                include_usage=include_usage,
                stream_options=stream_options if stream_options else None,
            )
            return StreamingResponse(generator, media_type="text/event-stream")
        return JSONResponse(result.body)

    return router


def _sse_format(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _openai_stream(
    result: CompletionResult,
    *,
    include_usage: bool,
    stream_options: dict | None,
) -> AsyncIterator[str]:
    chunk_plan = result.chunk_plan
    if not chunk_plan:
        yield _sse_format(result.body)
        yield "data: [DONE]\n\n"
        return

    base = result.body
    finish_reason = base["choices"][0]["finish_reason"]
    model = base["model"]
    completion_id = base["id"]
    created = base["created"]

    for idx, chunk in enumerate(chunk_plan.chunks, start=1):
        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created or int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk},
                    "finish_reason": None,
                }
            ],
        }
        if stream_options:
            payload["stream_options"] = stream_options
        yield _sse_format(payload)
        await apply_chunk_delay(chunk_plan, idx, chunk)

    final_payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created or int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": finish_reason,
            }
        ],
    }
    if stream_options:
        final_payload["stream_options"] = stream_options
    if include_usage:
        final_payload["usage"] = result.body.get("usage")
    yield _sse_format(final_payload)
    yield "data: [DONE]\n\n"

