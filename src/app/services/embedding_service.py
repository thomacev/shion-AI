# src/app/services/embedding_service.py
from app.core.config import settings
from app.core.exceptions import LLMServiceError
from app.core.gemini_client import get_gemini_client
from app.core.logger import logger


async def embed(
    texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
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
        logger.info(
            "Embedding batch generated successfully",
            extra={
                "batch_size": len(texts),
                "task_type": task_type,
                "model": settings.EMBEDDING_MODEL,
                "embedding_dim": settings.EMBEDDING_DIM,
            },
        )
    except Exception as e:
        logger.error(
            "Embedding generation failed",
            extra={
                "batch_size": len(texts),
                "task_type": task_type,
                "model": settings.EMBEDDING_MODEL,
                "error": str(e),
            },
            exc_info=True,
        )
        raise LLMServiceError("Embedding generation failed") from e

    return [e.values for e in response.embeddings]