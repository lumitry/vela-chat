# Mini-Mediator

A fixture-driven FastAPI server that emulates both OpenAI- and Ollama-compatible APIs for deterministic E2E testing. All behaviors (mirror, deterministic mapping, chain-of-thought, slow streaming pauses, rate limits, etc.) are data-backed so tests can evolve without touching Python.

## Running the server

```sh
conda activate velachat  # or your preferred env
cp tests/mocks/mini-mediator/.env_example tests/mocks/mini-mediator/.env
# adjust MINI_MEDIATOR_IP / MINI_MEDIATOR_PORT as needed
python tests/mocks/mini-mediator/mini_mediator.py --reload
```

- `--reload` enables uvicorn hot reload (recommended while editing fixtures or code).
- `--log-requests` enables request/response logging (see [Request Logging](#request-logging) below).
- `--log-file <path>` logs requests to a file instead of console.
- `--no-log-pretty` disables pretty-printing JSON in logs (default: pretty-printed).
- Environment overrides:
  - `MINI_MEDIATOR_IP` (default `localhost`)
  - `MINI_MEDIATOR_PORT` (default `11998`)
  - `MINI_MEDIATOR_RELOAD` (enable reload without CLI flag)
  - `MINI_MEDIATOR_CORS_ALLOW_ORIGINS` (comma-separated list)
  - `MINI_MEDIATOR_FIXTURES_DIR` (point to alternative fixtures root)
  - `MINI_MEDIATOR_LOG_REQUESTS` (enable request logging)
  - `MINI_MEDIATOR_LOG_FILE` (path to log file, or omit for console)
  - `MINI_MEDIATOR_LOG_PRETTY` (pretty-print JSON, default: `true`)

### `conda run` helpers

```sh
conda run -n velachat python tests/mocks/mini-mediator/mini_mediator.py
```

> ⚠️ `conda run` buffers stdout/stderr, so logs (including hot-reload notices) may appear only when the process exits. Prefer activating the env directly when debugging.

## Feature overview

- **OpenAI endpoints**: `/v1/models`, `/v1/chat/completions`, `/v1/embeddings` (placeholder), streaming SSE with token or chunky profiles, simulated pauses, and rate-limit errors via fixtures.
- **Ollama endpoints**: `/ollama/api/version`, `/tags`, `/generate`, `/chat` (JSON and streaming NDJSON).
- **Fixtures**: Stored under `fixtures/` (see [`fixtures/README.md`](./fixtures/README.md) for schema details). Edit JSON/YAML files and the server hot-reloads them automatically (disable with `MINI_MEDIATOR_WATCH_FIXTURES=false` if needed).
- **Chunk planner**: Automatically splits fixture responses into token-sized (~4 char) or chunked payloads, applies pause profiles, and throttles to a target tokens-per-second speed so UI tests can simulate both OpenAI- and Gemini-style latency.
- **Metadata**: Every response includes a `mini_mediator` block with the scenario name, metadata tags, and streaming plan to simplify assertions in Playwright.

## Request Logging

Mini-Mediator can log all HTTP requests and responses for debugging E2E tests. Logs include:

- Request method, path, and query parameters
- Request body (parsed as JSON if possible)
- Response status code and body (or indicator for streaming responses)
- Request duration in milliseconds

**Enable via CLI:**

```sh
python tests/mocks/mini-mediator/mini_mediator.py --log-requests
python tests/mocks/mini-mediator/mini_mediator.py --log-requests --log-file requests.log
python tests/mocks/mini-mediator/mini_mediator.py --log-requests --no-log-pretty
```

**Enable via environment variable:**

```sh
export MINI_MEDIATOR_LOG_REQUESTS=true
export MINI_MEDIATOR_LOG_FILE=requests.log  # optional
export MINI_MEDIATOR_LOG_PRETTY=false  # optional
```

Logs are pretty-printed JSON by default, making them easy to read. The `/healthz` endpoint is excluded from logging.

## Editing fixtures

1. Modify or add files under `tests/mocks/mini-mediator/fixtures/`.
2. Save the file—when running with `--reload`, the server automatically reloads fixtures and recomputes chunk plans.
3. Point Playwright tests to the relevant model slug (e.g., `mini-mediator:deterministic`) so conversations use the deterministic behavior you defined.

See [`fixtures/README.md`](./fixtures/README.md) for matchers, streaming options, and examples (autocomplete, chain-of-thought, slow streams, rate limits).

## Upcoming (potential) enhancements

- Automatic cache builder for extremely large fixture sets.
- Additional APIs (embeddings, tools, web search, images, code execution) once the tests require them.

Contributions welcome! Keep fixtures deterministic and add plenty of metadata so tests can assert on the exact scenario that fired.
