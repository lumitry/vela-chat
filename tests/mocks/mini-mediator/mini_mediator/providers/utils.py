from __future__ import annotations

import asyncio

from ..streaming import ChunkPlan


async def apply_chunk_delay(plan: ChunkPlan, chunk_index: int, chunk_text: str) -> None:
    delay = 0.0
    if plan.target_tokens_per_second:
        approx_tokens = max(len(chunk_text) / max(plan.chars_per_token, 1), 1)
        delay += approx_tokens / plan.target_tokens_per_second
    for event in plan.pause_events:
        if event.after_chunk == chunk_index:
            delay += max(event.seconds, 0)
    if delay > 0:
        await asyncio.sleep(delay)

