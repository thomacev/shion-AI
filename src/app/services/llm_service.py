import asyncio
from app.core.config import settings
from app.core.exceptions import LLMServiceError
from app.core.gemini_client import get_gemini_client
from app.core.logger import logger

RETRYABLE_ATTEMPTS = 2


def _to_gemini_contents(messages: list[dict]) -> list[dict]:
    """OpenAI uses 'assistant', Gemini uses 'model' for the same role."""
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
            logger.warning(
                "LLM generation failed, scheduling retry",
                extra={
                    "attempt": attempt,
                    "max_attempts": RETRYABLE_ATTEMPTS,
                    "model": model_to_use,
                    "error": str(e),
                },
            )
            if attempt < RETRYABLE_ATTEMPTS:
                await asyncio.sleep(1.5 * attempt)
    else:
        logger.error(
            "LLM generation failed after all retries",
            extra={
                "max_attempts": RETRYABLE_ATTEMPTS,
                "model": model_to_use,
                "error": str(last_error),
            },
            exc_info=True,
        )
        raise LLMServiceError("Model request failed after retries")

    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)

    logger.info(
        "LLM response generated successfully",
        extra={
            "model": model_to_use,
            "tokens_input": input_tokens,
            "tokens_output": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "message_count": len(messages),
        },
    )

    return {
        "content": response.text,
        "tokens_input": input_tokens,
        "tokens_output": output_tokens,
        "model": model_to_use,
    }