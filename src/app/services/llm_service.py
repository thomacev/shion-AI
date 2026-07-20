from openai import AsyncOpenAI, APITimeoutError, APIStatusError, APIConnectionError
from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import LLMServiceError
import asyncio


# The client is instantiated once (singleton pattern) and reused
# across requests, avoiding opening a new connection each time.
_client: AsyncOpenAI | None = None

RETRYABLE_ATTEMPTS = 2  
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

def get_llm_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=settings.OPENROUTER_API_KEY,
            timeout=30.0,  # Never wait more than 30s for OpenRouter to respond
        )
    return _client


async def chat(
    system_prompt: str,
    messages: list[dict],
    model: str | None = None,
) -> dict:
    """
    Calls the LLM using a system prompt and conversation history.

    `messages` format:
    [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "..."}]
    """
    client = get_llm_client()
    model_to_use = model or settings.MODEL_NAME

    # The system prompt always comes first — defines the assistant's persona
    # for the entire conversation.
    full_messages = [{"role": "system", "content": system_prompt}, *messages]

    last_error: Exception | None = None
    for attempt in range(RETRYABLE_ATTEMPTS + 1):
        try:
            response = await client.chat.completions.create(
                model=model_to_use,
                messages=full_messages,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            break
        except (APITimeoutError, APIConnectionError) as e:
            last_error = e
            logger.warning("llm_retryable_error", attempt=attempt, error=type(e).__name__)
        except APIStatusError as e:
            if e.status_code not in RETRYABLE_STATUS_CODES:
                # 401, 400, etc — no tiene sentido reintentar, cortamos ya
                logger.error("llm_status_error", status_code=e.status_code)
                raise LLMServiceError(f"OpenRouter returned an error: {e.status_code}")
            last_error = e
            logger.warning("llm_retryable_status", attempt=attempt, status_code=e.status_code)
        if attempt < RETRYABLE_ATTEMPTS:
            await asyncio.sleep(1.5 * attempt)  # wait a bit before retrying
    else:
        logger.error("llm_all_retries_failed", error=type(last_error))
        raise LLMServiceError("Failed to get a response from the LLM service after multiple attempts.")

    result = {
        "content": response.choices[0].message.content,
        "tokens_input": response.usage.prompt_tokens,
        "tokens_output": response.usage.completion_tokens,
        "model": model_to_use,
    }

    logger.info(
        "llm_response_received",
        model=model_to_use,
        tokens_input=result["tokens_input"],
        tokens_output=result["tokens_output"],
    )

    return result