import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar

import httpx
from google import genai
from google.genai import errors, types

from app.core.config import settings
from app.core.exceptions import LLMServiceError, RetryableLLMServiceError

_client: genai.Client | None = None
_task_client: ContextVar[genai.Client | None] = ContextVar("gemini_task_client", default=None)


def _new_client() -> genai.Client:
    return genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(
        timeout=settings.PROVIDER_TIMEOUT_SECONDS * 1000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ))


def get_gemini_client() -> genai.Client:
    global _client
    client = _task_client.get()
    if client is not None:
        return client
    if _client is None:
        _client = _new_client()
    return _client


@asynccontextmanager
async def task_gemini_client():
    client = _new_client()
    token = _task_client.set(client)
    try:
        yield client
    finally:
        _task_client.reset(token)
        await client.aio.aclose()
        client.close()


async def close_gemini_client():
    global _client
    if _client is not None:
        await _client.aio.aclose()
        _client.close()
        _client = None


async def provider_request(operation):
    """Bound provider retries; never retry invalid input or authentication errors."""
    for attempt in range(2):
        try:
            async with asyncio.timeout(settings.PROVIDER_TIMEOUT_SECONDS):
                return await operation()
        except (TimeoutError, httpx.TransportError) as exc:
            error = exc
        except errors.APIError as exc:
            if exc.code not in (408, 429, 500, 502, 503, 504):
                raise LLMServiceError("Model rejected the request") from exc
            error = exc
        if attempt == 0:
            await asyncio.sleep(1)
    raise RetryableLLMServiceError("Model service temporarily unavailable") from error
