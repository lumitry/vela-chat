# Mini-Mediator Fixture Schema

Deterministic behavior lives entirely inside `tests/mocks/mini-mediator/fixtures/`. Both the OpenAI and Ollama routers read the same files, so adding a new “model” is mostly data work.

```
fixtures/
  models/          # Chat + task models (mirror, CoT, rate-limit…)
  embeddings/      # Embedding fixtures (future)
  tools/           # Tool/function-call fixtures (future)
  images/          # Image-generation fixtures (future)
  web/             # Web-search fixtures (future)
```

## Scenario Schema

Each file contains `{ "model": "<slug>", "scenarios": [ ... ] }`. A scenario looks like:

```json
{
	"match": {
		"type": "exact",
		"role": "user",
		"text": "What's 9+TeN=?"
	},
	"response": {
		"message": "Twenty1",
		"think": null,
		"tool_calls": [],
		"attachments": []
	},
	"usage": {
		"prompt": 10,
		"completion": 3
	},
	"streaming": {
		"profile": "token",
		"pause_profile": {
			"before_first_chunk": 0,
			"mid_stream": [],
			"after_final_chunk": 0
		},
		"finish_reason": "stop",
		"chars_per_token": 4,
		"chunk_batch_size": 10,
		"target_tokens_per_second": 20
	},
	"error": null,
	"metadata": {
		"scenario": "autocomplete"
	}
}
```

### Fields

- `match`: How to decide if the scenario applies.
  - `type`: `exact`, `regex`, or `any`.
  - `role`: Optional role filter.
  - `text`: Value or regex.
  - `metadata`: Optional extra constraints (e.g., `{"feature": "tasks"}`).
- `response`: Deterministic payload.
  - `message`: Final assistant text.
  - `think`: Optional `<think></think>` content for CoT tests.
  - `tool_calls`: Array of serialized tool/function call payloads.
  - `attachments`: Deterministic citations, etc.
- `usage`: Prompt/completion/total tokens VelaChat expects.
- `streaming`: How to emit the response.
  - `profile`: `token` (~4-char slices) or `chunky` (batches of 10 token-slices).
  - `pause_profile`: When to sleep (arrays of `{ "after_chunk": N, "seconds": X }`).
  - `finish_reason`: `stop`, `length`, `content_filter`, etc.
  - `chars_per_token` & `chunk_batch_size`: override defaults per scenario.
  - `target_tokens_per_second`: throttle overall stream duration.
- `error`: If non-null, describes the deterministic error/HTTP status to emit (used for rate-limit models).
- `metadata`: Free-form tagging that Playwright tests can reference.
