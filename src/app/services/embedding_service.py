# src/app/services/embedding_service.py
from app.core.gemini_client import get_gemini_client
from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import LLMServiceError


async def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    client = get_gemini_client()
    try:
        response = await client.aio.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=texts,
            config={
                "task_type": task_type,
                "output_dimensionality": settings.EMBEDDING_DIM,
            },
        )
    except Exception as e:
        logger.error("embedding_error", error=str(e))
        raise LLMServiceError("Embedding generation failed") from e

    return [e.values for e in response.embeddings]