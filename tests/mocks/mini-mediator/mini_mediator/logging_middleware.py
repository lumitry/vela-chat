from __future__ import annotations

import json
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses with pretty-printed JSON."""

    def __init__(
        self,
        app: Callable,
        *,
        enabled: bool = True,
        log_file: str | None = None,
        pretty: bool = True,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.pretty = pretty
        
        # Set up logger
        self.logger = logging.getLogger("mini_mediator.requests")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create handler (file or console)
        if log_file:
            handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        else:
            handler = logging.StreamHandler()
        
        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.propagate = False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        # Skip health check endpoint
        if request.url.path == "/healthz":
            return await call_next(request)

        start_time = time.time()
        
        # Capture request body
        request_body = await self._get_request_body(request)
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Capture response body
        response_body = await self._get_response_body(response)
        
        # Log the request/response
        self._log_request_response(
            request=request,
            response=response,
            request_body=request_body,
            response_body=response_body,
            duration=duration,
        )
        
        return response

    async def _get_request_body(self, request: Request) -> dict | str | None:
        """Extract request body as JSON or string."""
        try:
            body = await request.body()
            if not body:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If not JSON, return as string (truncated if too long)
                body_str = body.decode("utf-8", errors="replace")
                return body_str[:1000] if len(body_str) > 1000 else body_str
        except Exception:
            return None

    async def _get_response_body(self, response: Response) -> dict | str | None:
        """Extract response body as JSON or string."""
        try:
            # Check if it's a streaming response
            if hasattr(response, "body_iterator") or getattr(response, "media_type", "").startswith("text/event-stream"):
                return "<streaming response>"
            
            # For non-streaming responses, try to read the body
            # Note: This only works if the body hasn't been consumed yet
            if hasattr(response, "body"):
                body = response.body
                if body:
                    try:
                        return json.loads(body)
                    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                        body_str = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
                        return body_str[:1000] if len(body_str) > 1000 else body_str
            
            # If body is not available, check media type to provide context
            media_type = getattr(response, "media_type", None)
            if media_type:
                return f"<{media_type} response>"
        except Exception:
            pass
        return None

    def _log_request_response(
        self,
        request: Request,
        response: Response,
        request_body: dict | str | None,
        response_body: dict | str | None,
        duration: float,
    ) -> None:
        """Log request and response in a structured format."""
        log_entry = {
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params) if request.query_params else None,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
            "request_body": request_body,
            "response_body": response_body,
        }
        
        # Format the log entry
        if self.pretty:
            log_message = json.dumps(log_entry, indent=2, ensure_ascii=False)
        else:
            log_message = json.dumps(log_entry, ensure_ascii=False)
        
        self.logger.info(f"\n{'='*80}\n{log_message}\n{'='*80}")

