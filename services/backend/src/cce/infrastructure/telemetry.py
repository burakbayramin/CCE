import json
import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("cce.requests")


def configure_logging() -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class RequestTelemetry:
    """Allowlisted JSON fields only: no URLs, headers, bodies or exception text."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw = dict(scope.get("headers", [])).get(b"x-request-id", b"")
        try:
            request_id = str(UUID(raw.decode("ascii")))
        except (ValueError, UnicodeDecodeError):
            request_id = str(uuid4())
        status = 500
        started = perf_counter()
        response_started = False

        async def send_response(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                message["headers"] = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() not in {b"x-request-id", b"cache-control"}
                ] + [(b"x-request-id", request_id.encode()), (b"cache-control", b"no-store")]
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except Exception as error:
            # Preserve only an allowlisted class name and the public request ID;
            # exception text/tracebacks can contain private DSNs or tokens.
            logger.error(
                json.dumps(
                    {
                        "event": "http_exception",
                        "request_id": request_id,
                        "exception_type": type(error).__name__,
                    }
                )
            )
            if not response_started:
                await send_response(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send_response(
                    {
                        "type": "http.response.body",
                        "body": b'{"detail":"Internal server error"}',
                    }
                )
            else:
                # Response already started: propagate a sanitized exception only.
                raise RuntimeError("Response interrupted") from None
        finally:
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "status": status,
                        "duration_ms": round((perf_counter() - started) * 1000, 2),
                    }
                )
            )
