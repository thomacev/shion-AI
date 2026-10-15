from app.core.config import settings
from app.core.exceptions import LLMServiceError, ValidationError
from app.core.gemini_client import get_gemini_client, provider_request
from app.core.logger import logger


def _to_gemini_contents(messages: list[dict]) -> list[dict]:
    return [{"role": "model" if m["role"] == "assistant" else m["role"],
             "parts": [{"text": m["content"]}]} for m in messages]


def _token_count(metadata, field):
    value = getattr(metadata, field, None)
    return value if isinstance(value, int) and value >= 0 else None


async def chat(system_prompt: str, messages: list[dict], model: str | None = None) -> dict:
    client = get_gemini_client()
    model_to_use = model or settings.MODEL_NAME
    contents = _to_gemini_contents(messages)
    count = await provider_request(lambda: client.aio.models.count_tokens(
        # Developer API count_tokens does not accept system_instruction config.
        # Count its text as an additional content and reserve role/format overhead.
        model=model_to_use, contents=[{"role": "user", "parts": [{"text": system_prompt}]}, *contents],
    ))
    total = getattr(count, "total_tokens", None)
    if not isinstance(total, int):
        raise LLMServiceError("Model did not return a prompt token count")
    if total + 256 > settings.MAX_PROMPT_TOKENS:
        raise ValidationError("Conversation exceeds the prompt token budget; start a new conversation")
    response = await provider_request(lambda: client.aio.models.generate_content(
        model=model_to_use, contents=contents,
        config={"system_instruction": system_prompt, "max_output_tokens": settings.LLM_MAX_TOKENS,
                "temperature": settings.LLM_TEMPERATURE},
    ))
    content = getattr(response, "text", None)
    if not isinstance(content, str) or not content.strip():
        raise LLMServiceError("Model returned no usable text (empty or blocked response)")
    metadata = getattr(response, "usage_metadata", None)
    input_tokens = _token_count(metadata, "prompt_token_count")
    output_tokens = _token_count(metadata, "candidates_token_count")
    logger.info("LLM response generated", model=model_to_use,
                tokens_input=input_tokens, tokens_output=output_tokens)
    return {"content": content.strip(), "tokens_input": input_tokens,
            "tokens_output": output_tokens, "model": model_to_use}
