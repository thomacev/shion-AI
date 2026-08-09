# src/app/core/gemini_client.py
from google import genai
from app.core.config import settings
from app.core.logger import logger

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    global _client
    if _client is None:
        logger.info("Initializing Gemini API client")
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client