# Mini-Mediator Requirements Digest

This document distills every referenced Mini-Mediator capability from the current E2E testing docs so we always know which behaviors must stay deterministic.

## Provider/Endpoint Expectations

- OpenAI-compatible base URL `http://localhost:11998/v1`
  - `/v1/models`
  - `/v1/chat/completions`
  - `/v1/embeddings` (placeholder today, must exist for Admin setup flows)
  - `/v1/responses` (future hook)
- Ollama-compatible namespace `http://localhost:11998/ollama`
  - `/ollama/api/version`
  - `/ollama/api/tags`
  - `/ollama/api/generate`
  - `/ollama/api/chat`
- Able to act as:
  - Default embedding model
  - Internal and external task model
  - Default OpenAI + Ollama chat connections in onboarding (`tests/e2e/Setup.setup.ts`)

## Deterministic Behavior Matrix

| Behavior | Referenced tests/use cases | Notes |
| --- | --- | --- |
| Mirror payload | Smoke/chat sanity | Current default; echoes request JSON |
| Deterministic map | Admin settings, general chat, autocomplete, tasks | Exact input → output mapping keyed by fixture |
| Chain-of-thought | Reasoning parsing tests | Wraps mapped output with `<think>` blocks |
| Slow/paused stream | `ENABLE_REALTIME_CHAT_SAVE`, timeout handling | Emit a few chunks, pause ~10s, resume |
| Rate-limit/error | Resilience, retry flows | Always 429 with retry headers, optionally mid-stream |
| Task suite outputs | Title, tags, query, emoji, image prompt, function-call tests | Deterministic JSON payloads |
| Autocomplete phrase | Rich text autocomplete | `9+10=` → “THIS IS A TEST OF MINI-MEDIATOR'S AUTOCOMPLETE SYSTEM.” |
| Embedding stub | Knowledge base, hybrid search | Fixed-length vector (allow 0-vector fallback) |
| Split/multi-model compatibility | Split view chats, MOA merges | Determinism must hold for concurrent calls |

## Streaming + Latency Expectations

- Two streaming profiles:
  - `token`: ~4 characters per chunk (simulates token streaming)
  - `chunky`: groups ~10 of those token chunks (Gemini-style bursts)
- Configurable pause profile:
  - e.g., emit 2 chunks → sleep 10s → emit remainder
  - Optional jitter/delay per chunk
- Target tokens-per-second throttle:
  - Given total characters and `chars_per_token`, pace chunk emission so full response duration ≈ `(total_chars / chars_per_token) / target_tokens_per_second`
  - Nice-to-have with pause profiles; okay if mid-stream pause overrides pacing
- Non-streaming fallback still required (aggregate chunks or original response)

## Error Handling

- Distinct finish reasons (`stop`, `length`, `content_filter`)
- Ability to truncate stream intentionally
- Retry headers for rate limits

## Future Hooks (Not Yet Implemented)

- Richer embeddings (beyond placeholder)
- Web search proxy
- Image generation
- Code execution / interpreter responses
- TTS/STT mocks

Architecture must leave room for new endpoints and additional “models” with minimal plumbing (ideally just add fixture entries).

