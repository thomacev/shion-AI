# app/core/middleware.py
import time
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.logger import logger


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )

        response = await call_next(request)
        process_time = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        if request.url.path != "/health":
            logger.info(
                "HTTP request processed",
                extra={
                    "status_code": response.status_code,
                    "duration_ms": process_time,
                },
            )

        return response

class UploadBodyLimitMiddleware:
    """Limit streamed multipart bytes before FastAPI parses uploaded files."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        from starlette.formparsers import MultiPartException
        from starlette.responses import JSONResponse
        from app.core.config import settings

        if scope["type"] != "http" or scope["method"] != "POST" or "/documents" not in scope["path"]:
            return await self.app(scope, receive, send)
        limit = settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024 + 65536
        length = dict(scope.get("headers", [])).get(b"content-length")
        if length is not None:
            try:
                size = int(length)
                if size < 0:
                    raise ValueError
            except ValueError:
                return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
            if size > limit:
                return await JSONResponse({"detail": "Upload request too large"}, status_code=413)(scope, receive, send)
        consumed = 0
        too_large = False

        async def limited_receive():
            nonlocal consumed, too_large
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    too_large = True
                    # The multipart parser closes its temporary files for this exception.
                    raise MultiPartException("Upload request too large")
            return message

        async def limited_send(message):
            if too_large:
                if message["type"] == "http.response.start":
                    await JSONResponse({"detail": "Upload request too large"}, status_code=413)(scope, receive, send)
                return
            await send(message)

        await self.app(scope, limited_receive, limited_send)
