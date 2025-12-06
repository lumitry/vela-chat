from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..engine import CompletionResult, MiniMediatorEngine
from ..providers.utils import apply_chunk_delay


def build_router(engine: MiniMediatorEngine) -> APIRouter:
    router = APIRouter(prefix="/ollama/api", tags=["ollama"])

    @router.get("/tags")
    async def list_tags() -> JSONResponse:
        models = engine.list_models()["data"]
        now = _now_iso()
        payload = {
            "models": [
                {
                    "name": model["id"],
                    "model": model["id"],
                    "modified_at": now,
                    "size": 0,
                    "digest": "mini-mediator",
                }
                for model in models
            ]
        }
        return JSONResponse(payload)

    @router.get("/version")
    async def version() -> Dict[str, Any]:
        return {"version": "99.99.99"}

    @router.post("/generate")
    async def generate(request: Request):
        body = await request.json()
        # Ollama /generate uses "prompt" (string), not "messages" (array)
        prompt = body.get("prompt", "")
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            # Fallback: try to extract messages if prompt is not provided
            messages = _extract_messages(body)
        payload = {
            "model": body.get("model"),
            "messages": messages,
        }
        result = engine.chat_completion(payload)
        if result.error:
            raise HTTPException(
                status_code=result.error.status_code,
                detail=result.error.body.get("error"),
                headers=result.error.headers,
            )
        stream = body.get("stream", True)
        if stream and result.chunk_plan:
            return StreamingResponse(
                _ollama_generate_stream(result),
                media_type="application/x-ndjson",
            )
        response = _ollama_generate_sync_response(result)
        return JSONResponse(response)

    @router.post("/chat")
    async def chat(request: Request):
        body = await request.json()
        messages = _extract_messages(body)
        payload = {
            "model": body.get("model"),
            "messages": messages,
        }
        result = engine.chat_completion(payload)
        if result.error:
            raise HTTPException(
                status_code=result.error.status_code,
                detail=result.error.body.get("error"),
                headers=result.error.headers,
            )
        stream = body.get("stream", True)
        if stream and result.chunk_plan:
            return StreamingResponse(
                _ollama_chat_stream(result),
                media_type="application/x-ndjson",
            )
        response = _ollama_chat_sync_response(result)
        return JSONResponse(response)

    return router


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ollama_generate_sync_response(result: CompletionResult) -> Dict[str, Any]:
    """Ollama /generate endpoint sync response format (uses 'response' string field)."""
    body = result.body
    message = body["choices"][0]["message"]
    return {
        "model": body["model"],
        "created_at": _now_iso(),
        "response": message["content"],
        "done": True,
        "context": [],
        "total_duration": _estimate_duration(body),
        "load_duration": 50_000_000,
        "prompt_eval_count": body["usage"]["prompt_tokens"],
        "prompt_eval_duration": _estimate_prompt_duration(body),
        "eval_count": body["usage"]["completion_tokens"],
        "eval_duration": _estimate_eval_duration(body),
    }


def _ollama_chat_sync_response(result: CompletionResult) -> Dict[str, Any]:
    """Ollama /chat endpoint sync response format (uses 'message' object field)."""
    body = result.body
    message = body["choices"][0]["message"]
    return {
        "model": body["model"],
        "created_at": _now_iso(),
        "message": {"role": "assistant", "content": message["content"]},
        "done": True,
        "done_reason": body["choices"][0].get("finish_reason"),
        "context": [],
        "total_duration": _estimate_duration(body),
        "load_duration": 50_000_000,
        "prompt_eval_count": body["usage"]["prompt_tokens"],
        "prompt_eval_duration": _estimate_prompt_duration(body),
        "eval_count": body["usage"]["completion_tokens"],
        "eval_duration": _estimate_eval_duration(body),
    }


async def _ollama_generate_stream(result: CompletionResult) -> AsyncIterator[str]:
    """Ollama /generate endpoint streaming format (uses 'response' string field)."""
    chunk_plan = result.chunk_plan
    body = result.body
    if not chunk_plan:
        yield json.dumps(_ollama_generate_sync_response(result)) + "\n"
        return

    for idx, chunk in enumerate(chunk_plan.chunks, start=1):
        payload = {
            "model": body["model"],
            "created_at": _now_iso(),
            "response": chunk,
            "done": False,
        }
        yield json.dumps(payload) + "\n"
        await apply_chunk_delay(chunk_plan, idx, chunk)

    final_payload = {
        "model": body["model"],
        "created_at": _now_iso(),
        "response": "",
        "done": True,
        "context": [],
        "total_duration": _estimate_duration(body),
        "load_duration": 50_000_000,
        "prompt_eval_count": body["usage"]["prompt_tokens"],
        "prompt_eval_duration": _estimate_prompt_duration(body),
        "eval_count": body["usage"]["completion_tokens"],
        "eval_duration": _estimate_eval_duration(body),
    }
    yield json.dumps(final_payload) + "\n"


async def _ollama_chat_stream(result: CompletionResult) -> AsyncIterator[str]:
    """Ollama /chat endpoint streaming format (uses 'message' object field)."""
    chunk_plan = result.chunk_plan
    body = result.body
    if not chunk_plan:
        yield json.dumps(_ollama_chat_sync_response(result)) + "\n"
        return

    for idx, chunk in enumerate(chunk_plan.chunks, start=1):
        payload = {
            "model": body["model"],
            "created_at": _now_iso(),
            "message": {"role": "assistant", "content": chunk},
            "done": False,
        }
        yield json.dumps(payload) + "\n"
        await apply_chunk_delay(chunk_plan, idx, chunk)

    final_payload = {
        "model": body["model"],
        "created_at": _now_iso(),
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "done_reason": body["choices"][0].get("finish_reason"),
        "context": [],
        "total_duration": _estimate_duration(body),
        "load_duration": 50_000_000,
        "prompt_eval_count": body["usage"]["prompt_tokens"],
        "prompt_eval_duration": _estimate_prompt_duration(body),
        "eval_count": body["usage"]["completion_tokens"],
        "eval_duration": _estimate_eval_duration(body),
    }
    yield json.dumps(final_payload) + "\n"


def _extract_messages(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    messages = body.get("messages")
    if isinstance(messages, list) and messages:
        return messages
    prompt = body.get("prompt")
    if isinstance(prompt, str):
        return [{"role": "user", "content": prompt}]
    return []


def _estimate_duration(body: Dict[str, Any]) -> int:
    usage = body.get("usage", {})
    tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    return max(500_000_000, tokens * 7_500_000)


def _estimate_prompt_duration(body: Dict[str, Any]) -> int:
    usage = body.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    return max(30_000_000, prompt_tokens * 2_500_000)


def _estimate_eval_duration(body: Dict[str, Any]) -> int:
    usage = body.get("usage", {})
    completion_tokens = usage.get("completion_tokens", 0)
    return max(400_000_000, completion_tokens * 5_000_000)

