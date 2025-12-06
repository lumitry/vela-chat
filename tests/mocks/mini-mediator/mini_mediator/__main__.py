from __future__ import annotations

import uvicorn

from . import create_app, get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        create_app(),
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
    )


if __name__ == "__main__":
    main()

