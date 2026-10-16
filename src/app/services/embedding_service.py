import math

from app.core.config import settings
from app.core.exceptions import LLMServiceError
from app.core.gemini_client import get_gemini_client, provider_request


def validate_embeddings(vectors, expected_count: int) -> None:
    if not isinstance(vectors, list) or len(vectors) != expected_count:
        raise LLMServiceError("Embedding response did not cover every document chunk")
    for vector in vectors:
        if (not isinstance(vector, list) or len(vector) != settings.EMBEDDING_DIM
                or any(isinstance(x, bool) or not isinstance(x, (int, float))
                       or not math.isfinite(x) for x in vector)
                or not any(x != 0 for x in vector)):
            raise LLMServiceError("Embedding response contained an invalid vector")


async def embed(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    if not texts or any(not text.strip() for text in texts):
        raise LLMServiceError("Cannot embed empty text")
    client = get_gemini_client()
    vectors = []
    for start in range(0, len(texts), settings.EMBEDDING_BATCH_SIZE):
        batch = texts[start:start + settings.EMBEDDING_BATCH_SIZE]
        response = await provider_request(lambda batch=batch: client.aio.models.embed_content(
            model=settings.EMBEDDING_MODEL, contents=batch,
            config={"task_type": task_type, "output_dimensionality": settings.EMBEDDING_DIM},
        ))
        embeddings = getattr(response, "embeddings", None)
        values = [getattr(item, "values", None) for item in embeddings] if embeddings else []
        validate_embeddings(values, len(batch))
        vectors.extend(values)
    return vectors
