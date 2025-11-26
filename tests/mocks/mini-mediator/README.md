# Mini Mediator

A lightweight OpenAI API-compliant (ish) Python server to mock LLMs for testing purposes.

Note that using it currently requires disabling response streaming in VelaChat.

Remember to set the `MINI_MEDIATOR_IP` environment variable to the IP address of the machine running this server, or it will default to `localhost`, which might not be accessible from the client you're testing with. See the `.env_example` file for an example of how to set this up.

## How to Run

```sh
conda activate velachat  # or your preferred env
cp tests/mocks/mini-mediator/.env_example tests/mocks/mini-mediator/.env
nvim tests/mocks/mini-mediator/.env  # Edit the IP/port if needed
python tests/mocks/mini-mediator/mini_mediator.py --reload # reload for local development
```

- Use `--reload` to enable uvicorn's hot reload for local development (files must be accessible from the activated environment; won't work with `conda run`).
- Default host/port come from `.env`; override with `MINI_MEDIATOR_IP` / `MINI_MEDIATOR_PORT`.

## Running via `conda run`

When a shell can't activate the env (e.g., automation), you can still launch it with:

```sh
conda run -n velachat python tests/mocks/mini-mediator/mini_mediator.py
```

Local E2E testing will probably use:

```sh
conda run -n $CONDA_ENV python tests/mocks/mini-mediator/mini_mediator.py
```

Note: `conda run` buffers stdout/stderr, so logs (including the startup banner) may stay hidden until the process exits. Prefer activating the env directly when you need live logs or `--reload`.
