from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence


@dataclass
class PauseEvent:
    after_chunk: int
    seconds: float


@dataclass
class ChunkPlan:
    profile: str
    chunks: List[str]
    chars_per_token: int
    chunk_batch_size: int
    pause_events: List[PauseEvent] = field(default_factory=list)
    target_tokens_per_second: float | None = None

    def to_dict(self) -> dict:
        return {
            "profile": self.profile,
            "chunks": self.chunks,
            "chars_per_token": self.chars_per_token,
            "chunk_batch_size": self.chunk_batch_size,
            "pause_events": [
                {"after_chunk": event.after_chunk, "seconds": event.seconds}
                for event in self.pause_events
            ],
            "target_tokens_per_second": self.target_tokens_per_second,
        }


def build_chunk_plan(
    text: str,
    *,
    profile: str,
    chars_per_token: int,
    chunk_batch_size: int,
    pause_events: Sequence[PauseEvent] | None = None,
    target_tokens_per_second: float | None = None,
) -> ChunkPlan:
    tokens = _split_text(text, max(chars_per_token, 1))
    chunks = (
        tokens
        if profile == "token"
        else _group_tokens(tokens, max(chunk_batch_size, 1))
    )
    return ChunkPlan(
        profile=profile,
        chunks=chunks,
        chars_per_token=max(chars_per_token, 1),
        chunk_batch_size=max(chunk_batch_size, 1),
        pause_events=list(pause_events or []),
        target_tokens_per_second=target_tokens_per_second,
    )


def _split_text(text: str, step: int) -> List[str]:
    if not text:
        return [""]
    return [text[i : i + step] for i in range(0, len(text), step)]


def _group_tokens(tokens: Iterable[str], batch_size: int) -> List[str]:
    batch: List[str] = []
    grouped: List[str] = []
    for token in tokens:
        batch.append(token)
        if len(batch) == batch_size:
            grouped.append("".join(batch))
            batch = []
    if batch:
        grouped.append("".join(batch))
    return grouped or [""]

