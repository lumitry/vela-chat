from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fixtures import FixturesStore, Scenario, StreamingSpec
from .streaming import ChunkPlan, PauseEvent, build_chunk_plan


@dataclass
class ModelMeta:
    id: str
    created: int
    owned_by: str = "localhost"


@dataclass
class ErrorResponse:
    status_code: int
    body: Dict[str, Any]
    headers: Dict[str, str]


@dataclass
class CompletionResult:
    body: Dict[str, Any]
    chunk_plan: Optional[ChunkPlan]
    error: Optional[ErrorResponse]
    scenario: Optional[str] = None


class MiniMediatorEngine:
    """Central dispatcher that converts fixtures into deterministic responses."""

    def __init__(self, fixtures_store: Optional[FixturesStore] = None) -> None:
        self._fixtures = fixtures_store or FixturesStore()
        self._models: List[ModelMeta] = self._build_model_metadata()

    def _build_model_metadata(self) -> List[ModelMeta]:
        fixtures = self._fixtures.model_fixtures.values()
        metadata = [
            ModelMeta(
                id=fixture.model,
                created=fixture.created,
                owned_by=fixture.owned_by,
            )
            for fixture in fixtures
        ]
        if not metadata:
            metadata.extend(
                [
                    ModelMeta(id="mini-mediator", created=12345),
                    ModelMeta(id="mini-mediator:thinking", created=123456),
                ]
            )
        return metadata

    def list_models(self) -> Dict[str, Any]:
        data = [
            {
                "id": model.id,
                "object": "model",
                "created": model.created,
                "owned_by": model.owned_by,
            }
            for model in self._models
        ]
        return {"data": data}

    def reload_fixtures(self) -> None:
        self._fixtures.reload()
        self._models = self._build_model_metadata()

    @property
    def fixtures_root(self) -> Path:
        return self._fixtures.root

    def chat_completion(self, request_payload: Dict[str, Any]) -> CompletionResult:
        model_id = request_payload.get("model", "mini-mediator")
        scenario = self._fixtures.find_scenario(model_id, request_payload)
        if scenario:
            return self._from_scenario(model_id, scenario, request_payload)
        return self._mirror_response(model_id, request_payload)

    def _from_scenario(
        self, model_id: str, scenario: Scenario, payload: Dict[str, Any]
    ) -> CompletionResult:
        behavior = scenario.metadata.get("behavior") if scenario.metadata else None
        if behavior == "mirror":
            return self._mirror_response(
                model_id,
                payload,
                scenario_name=scenario.name or "mirror",
                metadata=scenario.metadata,
            )

        if scenario.error:
            headers = {}
            if scenario.error.retry_after is not None:
                headers["Retry-After"] = str(scenario.error.retry_after)
            return CompletionResult(
                body=scenario.error.body(),
                chunk_plan=None,
                error=ErrorResponse(
                    status_code=scenario.error.status_code,
                    body=scenario.error.body(),
                    headers=headers,
                ),
                scenario=scenario.name,
            )

        response_text = scenario.response.message
        if scenario.response.think:
            response_text = (
                f"<think>{scenario.response.think}</think>\n{scenario.response.message}"
            )

        chunk_plan = _build_plan_from_streaming(scenario.streaming, response_text)

        body = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text,
                        "refusal": None,
                        "annotations": [],
                    },
                    "logprobs": None,
                    "finish_reason": scenario.streaming.finish_reason or "stop",
                }
            ],
            "usage": {
                "prompt_tokens": scenario.usage.prompt,
                "completion_tokens": scenario.usage.completion,
                "total_tokens": scenario.usage.total,
            },
            "mini_mediator": {
                "scenario": scenario.name,
                "streaming": chunk_plan.to_dict() if chunk_plan else None,
                "metadata": scenario.metadata,
            },
        }

        return CompletionResult(
            body=body,
            chunk_plan=chunk_plan,
            error=None,
            scenario=scenario.name,
        )

    def _mirror_response(
        self,
        model_id: str,
        payload: Dict[str, Any],
        *,
        scenario_name: str = "mirror",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CompletionResult:
        pretty_json = json.dumps(payload, indent=2)
        message = f"Received request with data:\n```json\n{pretty_json}\n```"
        default_streaming = StreamingSpec()
        chunk_plan = _build_plan_from_streaming(default_streaming, message)

        body = {
            "id": "chatcmpl-mirror",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_id,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": message,
                        "refusal": None,
                        "annotations": [],
                    },
                    "logprobs": None,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 42,
                "completion_tokens": 42,
                "total_tokens": 84,
            },
            "mini_mediator": {
                "scenario": scenario_name,
                "streaming": chunk_plan.to_dict() if chunk_plan else None,
                "metadata": metadata or {},
            },
        }

        return CompletionResult(
            body=body,
            chunk_plan=chunk_plan,
            error=None,
            scenario=scenario_name,
        )


def _build_plan_from_streaming(
    streaming: StreamingSpec, response_text: str
) -> ChunkPlan:
    pause_events = [
        PauseEvent(after_chunk=event.after_chunk, seconds=event.seconds)
        for event in streaming.pause_profile
    ]
    return build_chunk_plan(
        response_text,
        profile=streaming.profile or "token",
        chars_per_token=streaming.chars_per_token or 4,
        chunk_batch_size=streaming.chunk_batch_size or 10,
        pause_events=pause_events,
        target_tokens_per_second=streaming.target_tokens_per_second,
    )

