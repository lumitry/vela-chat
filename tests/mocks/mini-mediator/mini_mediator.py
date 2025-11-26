from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from mini_mediator import create_app, get_settings

SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mini-Mediator mock server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable FastAPI auto-reload (development only)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    reload_enabled = args.reload or settings.reload

    print(
        f"Starting Mini-Mediator on {settings.host}:{settings.port} "
        f"(reload={reload_enabled})",
        flush=True,
    )

    target = "mini_mediator.app:create_app" if reload_enabled else create_app()
    uvicorn.run(
        target,
        host=settings.host,
        port=settings.port,
        reload=reload_enabled,
        reload_dirs=[str(SCRIPT_DIR)] if reload_enabled else None,
        log_level="info",
    )


if __name__ == "__main__":
    main()