from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

DEFAULT_FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURES_ENV_VAR = "MINI_MEDIATOR_FIXTURES_DIR"


class PauseConfig(BaseModel):
    after_chunk: int
    seconds: float


class StreamingDefaults(BaseModel):
    profile: str = "token"
    chars_per_token: int = 4
    chunk_batch_size: int = 10
    target_tokens_per_second: Optional[float] = None
    finish_reason: str = "stop"
    pause_profile: List[PauseConfig] = Field(default_factory=list)


class ScenarioMatch(BaseModel):
    type: str = "any"  # exact | regex | any
    role: Optional[str] = None
    text: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class ResponseSpec(BaseModel):
    message: str
    think: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class UsageSpec(BaseModel):
    prompt: int = 42
    completion: int = 42

    @property
    def total(self) -> int:
        return self.prompt + self.completion


class ErrorSpec(BaseModel):
    status_code: int = 500
    type: str = "mini_mediator_error"
    message: str = "Mini-Mediator simulated error"
    retry_after: Optional[float] = None

    def body(self) -> Dict[str, Any]:
        error_obj = {"type": self.type, "message": self.message}
        if self.retry_after is not None:
            error_obj["retry_after"] = self.retry_after
        return {"error": error_obj}


class StreamingSpec(BaseModel):
    profile: str = "token"
    chars_per_token: Optional[int] = None
    chunk_batch_size: Optional[int] = None
    target_tokens_per_second: Optional[float] = None
    finish_reason: Optional[str] = None
    pause_profile: List[PauseConfig] = Field(default_factory=list)

    def merged(self, defaults: StreamingDefaults) -> "StreamingSpec":
        return StreamingSpec(
            profile=self.profile or defaults.profile,
            chars_per_token=self.chars_per_token or defaults.chars_per_token,
            chunk_batch_size=self.chunk_batch_size or defaults.chunk_batch_size,
            target_tokens_per_second=self.target_tokens_per_second
            or defaults.target_tokens_per_second,
            finish_reason=self.finish_reason or defaults.finish_reason,
            pause_profile=self.pause_profile or list(defaults.pause_profile),
        )


class Scenario(BaseModel):
    name: Optional[str] = None
    match: ScenarioMatch = ScenarioMatch()
    response: ResponseSpec
    usage: UsageSpec = UsageSpec()
    streaming: StreamingSpec = StreamingSpec()
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[ErrorSpec] = None


class ModelFixture(BaseModel):
    model: str
    display_name: Optional[str] = None
    created: int = 0
    owned_by: str = "mini-mediator"
    defaults: StreamingDefaults = StreamingDefaults()
    scenarios: List[Scenario]

    def find_match(self, payload: Dict[str, Any]) -> Optional[Scenario]:
        messages: List[Dict[str, Any]] = payload.get("messages", [])
        metadata: Dict[str, Any] = payload.get("metadata", {})
        for scenario in self.scenarios:
            matcher = scenario.match
            if matcher.metadata:
                if any(
                    metadata.get(key) != value for key, value in matcher.metadata.items()
                ):
                    continue
            content = _select_message(messages, matcher.role)
            if matcher.type == "any":
                return scenario
            if content is None:
                continue
            if matcher.type == "exact" and matcher.text == content:
                return scenario
            if matcher.type == "regex" and matcher.text:
                if re.search(matcher.text, content):
                    return scenario
        return None


def _select_message(
    messages: List[Dict[str, Any]], role: Optional[str]
) -> Optional[str]:
    for message in reversed(messages):
        if role and message.get("role") != role:
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [part.get("text") for part in content if part.get("type") == "text"]
            joined = "".join(part for part in parts if part)
            if joined:
                return joined
    return None


class FixturesStore:
    def __init__(self, fixtures_root: Optional[Path] = None) -> None:
        configured = os.environ.get(FIXTURES_ENV_VAR)
        self.root = fixtures_root or Path(configured or DEFAULT_FIXTURES_ROOT)
        self.model_fixtures: Dict[str, ModelFixture] = {}
        self.reload()

    def reload(self) -> None:
        self.model_fixtures.clear()
        models_dir = self.root / "models"
        if not models_dir.exists():
            return
        for path in models_dir.glob("*.json"):
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            fixture = ModelFixture(**raw)
            self.model_fixtures[fixture.model] = fixture

    def available_models(self) -> List[Dict[str, Any]]:
        models = []
        for fixture in self.model_fixtures.values():
            models.append(
                {
                    "id": fixture.model,
                    "object": "model",
                    "created": fixture.created,
                    "owned_by": fixture.owned_by,
                }
            )
        return models

    def find_scenario(
        self, model_id: str, payload: Dict[str, Any]
    ) -> Optional[Scenario]:
        fixture = self.model_fixtures.get(model_id)
        if not fixture:
            return None
        scenario = fixture.find_match(payload)
        if scenario:
            merged = _copy_model(scenario)
            merged.streaming = scenario.streaming.merged(fixture.defaults)
            return merged
        return None


def _copy_model(model: BaseModel) -> BaseModel:
    if hasattr(model, "model_copy"):
        return model.model_copy(deep=True)  # type: ignore[attr-defined]
    return model.copy(deep=True)

