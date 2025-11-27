from __future__ import annotations

import argparse
import os
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
    parser.add_argument(
        "--log-requests",
        action="store_true",
        help="Enable request/response logging",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file (default: log to console)",
    )
    parser.add_argument(
        "--log-pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON in logs (default: True)",
    )
    parser.add_argument(
        "--no-log-pretty",
        dest="log_pretty",
        action="store_false",
        help="Disable pretty-printing JSON in logs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    reload_enabled = args.reload or settings.reload
    
    # Override logging settings from CLI if provided
    log_requests = args.log_requests or settings.log_requests
    log_file = args.log_file if args.log_file is not None else settings.log_file
    log_pretty = getattr(args, "log_pretty", None)
    if log_pretty is None:
        log_pretty = settings.log_pretty

    print(
        f"Starting Mini-Mediator on {settings.host}:{settings.port} "
        f"(reload={reload_enabled}, log_requests={log_requests})",
        flush=True,
    )

    # Create app with logging config
    # Note: When reload is enabled, we can't pass args directly, so we use env vars
    if reload_enabled:
        # Set environment variables for reload mode
        if args.log_requests:
            os.environ["MINI_MEDIATOR_LOG_REQUESTS"] = "true"
        if args.log_file is not None:
            os.environ["MINI_MEDIATOR_LOG_FILE"] = args.log_file
        if hasattr(args, "log_pretty") and args.log_pretty is not None:
            os.environ["MINI_MEDIATOR_LOG_PRETTY"] = "true" if args.log_pretty else "false"
        target = "mini_mediator.app:create_app"
    else:
        app = create_app(
            log_requests=log_requests,
            log_file=log_file,
            log_pretty=log_pretty,
        )
        target = app
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