# src/app/services/llm_service.py
from app.core.gemini_client import get_gemini_client
from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import LLMServiceError

RETRYABLE_ATTEMPTS = 2


def _to_gemini_contents(messages: list[dict]) -> list[dict]:
    """OpenAI usa 'assistant', Gemini usa 'model' para el mismo rol."""
    return [
        {
            "role": "model" if m["role"] == "assistant" else m["role"],
            "parts": [{"text": m["content"]}],
        }
        for m in messages
    ]


async def chat(
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
) -> dict:
    client = get_gemini_client()
    model_to_use = model or settings.MODEL_NAME
    contents = _to_gemini_contents(messages)

    last_error: Exception | None = None

    for attempt in range(1, RETRYABLE_ATTEMPTS + 1):
        try:
            response = await client.aio.models.generate_content(
                model=model_to_use,
                contents=contents,
                config={
                    "system_instruction": system_prompt,
                    "max_output_tokens": settings.LLM_MAX_TOKENS,
                    "temperature": settings.LLM_TEMPERATURE,
                },
            )
            break
        except Exception as e:
            last_error = e
            logger.warning("llm_retryable_error", attempt=attempt, error=str(e))
            if attempt < RETRYABLE_ATTEMPTS:
                import asyncio
                await asyncio.sleep(1.5 * attempt)
    else:
        logger.error("llm_all_retries_failed", error=str(last_error))
        raise LLMServiceError("Model request failed after retries")

    result = {
        "content": response.text,
        "tokens_input": response.usage_metadata.prompt_token_count,
        "tokens_output": response.usage_metadata.candidates_token_count,
        "model": model_to_use,
    }
    logger.info("llm_response_received", **{k: v for k, v in result.items() if k != "content"})
    return result