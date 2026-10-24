from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from google.genai.errors import APIError

from app.core.config import Settings, settings
from app.core.exceptions import (
    LLMServiceError,
    RetryableLLMServiceError,
    ValidationError,
)
from app.core.gemini_client import provider_request
from app.services.embedding_service import embed, validate_embeddings
from app.services.llm_service import chat


def client_with_response(response):
    models = SimpleNamespace(generate_content=AsyncMock(return_value=response),
        count_tokens=AsyncMock(return_value=SimpleNamespace(total_tokens=50)))
    return SimpleNamespace(aio=SimpleNamespace(models=models))


async def test_missing_usage_is_unknown_not_a_crash():
    fake = client_with_response(SimpleNamespace(text="answer", usage_metadata=SimpleNamespace(
        prompt_token_count=None, candidates_token_count=None)))
    with patch("app.services.llm_service.get_gemini_client", return_value=fake):
        result = await chat("instructions", [{"role": "user", "content": "question"}])
    assert result["content"] == "answer"
    assert result["tokens_output"] is None
    count_kwargs = fake.aio.models.count_tokens.call_args.kwargs
    assert "config" not in count_kwargs
    assert count_kwargs["contents"][0]["parts"][0]["text"] == "instructions"


@pytest.mark.parametrize("text", [None, "", "   "])
async def test_empty_generation_is_a_domain_error(text):
    with (
        patch("app.services.llm_service.get_gemini_client", return_value=client_with_response(SimpleNamespace(text=text))),
        pytest.raises(LLMServiceError),
    ):
        await chat("instructions", [{"role": "user", "content": "question"}])


async def test_prompt_budget_prevents_generation():
    fake = client_with_response(SimpleNamespace(text="answer"))
    fake.aio.models.count_tokens.return_value.total_tokens = settings.MAX_PROMPT_TOKENS + 1
    with patch("app.services.llm_service.get_gemini_client", return_value=fake), pytest.raises(ValidationError):
        await chat("instructions", [{"role": "user", "content": "question"}])
    fake.aio.models.generate_content.assert_not_awaited()


@pytest.mark.parametrize("code, calls, error_type", [(400, 1, LLMServiceError), (401, 1, LLMServiceError),
                                                   (429, 2, RetryableLLMServiceError), (503, 2, RetryableLLMServiceError)])
async def test_only_transient_errors_retry(code, calls, error_type):
    operation = AsyncMock(side_effect=APIError(code, {"error": {"message": "test", "code": code}}))
    with patch("app.core.gemini_client.asyncio.sleep", new=AsyncMock()), pytest.raises(error_type):
        await provider_request(operation)
    assert operation.await_count == calls


async def test_embedding_batches_preserve_order(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 2)
    async def response(**kwargs):
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[float(text)] * 1536) for text in kwargs["contents"]])
    method = AsyncMock(side_effect=response)
    fake = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=method)))
    with patch("app.services.embedding_service.get_gemini_client", return_value=fake):
        result = await embed(["1", "2", "3"])
    assert [vector[0] for vector in result] == [1, 2, 3]
    assert [call.kwargs["contents"] for call in method.call_args_list] == [["1", "2"], ["3"]]


@pytest.mark.parametrize("vector", [[0.0] * 1536, [float("nan")] * 1536, [float("inf")] * 1536,
                                    [True] * 1536, [1.0] * 768, None])
def test_invalid_embedding_rejected(vector):
    with pytest.raises(LLMServiceError):
        validate_embeddings([vector], 1)


def test_dimension_configuration_rejects_mismatch():
    from pydantic import ValidationError as SettingsError
    with pytest.raises(SettingsError):
        Settings(EMBEDDING_DIM=768)


async def test_structured_answer_schema_is_passed_to_gemini():
    from app.services.answer_grounding import HybridAnswer
    schema = HybridAnswer.model_json_schema()
    fake = client_with_response(SimpleNamespace(text='{"document_answer": "", "general_answer": "answer"}'))
    with patch("app.services.llm_service.get_gemini_client", return_value=fake):
        await chat("instructions", [{"role": "user", "content": "question"}], response_schema=schema)
    config = fake.aio.models.generate_content.call_args.kwargs["config"]
    assert config["response_mime_type"] == "application/json"
    assert config["response_json_schema"] == schema
