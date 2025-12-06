from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import List


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    host: str = os.environ.get("MINI_MEDIATOR_IP", "localhost")
    port: int = int(os.environ.get("MINI_MEDIATOR_PORT", 11998))
    reload: bool = _bool_env("MINI_MEDIATOR_RELOAD", False)
    watch_fixtures: bool = _bool_env("MINI_MEDIATOR_WATCH_FIXTURES", True)
    cors_allow_origins: List[str] = None  # type: ignore[assignment]
    log_requests: bool = _bool_env("MINI_MEDIATOR_LOG_REQUESTS", False)
    log_file: str | None = os.environ.get("MINI_MEDIATOR_LOG_FILE")
    log_pretty: bool = _bool_env("MINI_MEDIATOR_LOG_PRETTY", True)

    def __post_init__(self) -> None:
        # dataclass with frozen=True requires object.__setattr__
        origins = os.environ.get("MINI_MEDIATOR_CORS_ALLOW_ORIGINS", "*")
        values = [origin.strip() for origin in origins.split(",") if origin.strip()]
        object.__setattr__(self, "cors_allow_origins", values or ["*"])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

