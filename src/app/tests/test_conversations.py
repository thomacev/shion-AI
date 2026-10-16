import uuid
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest_asyncio

from app.core.exceptions import LLMServiceError
from app.models.document import DocumentChunk


@pytest_asyncio.fixture
async def test_conversation(client, auth_headers, test_assistant):
    response = await client.post(
        f"/assistants/{test_assistant['id']}/conversations",
        json={"title": "First chat"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


class TestCreateConversation:
    async def test_create_success(self, client, auth_headers, test_assistant):
        response = await client.post(
            f"/assistants/{test_assistant['id']}/conversations",
            json={"title": "New chat"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["title"] == "New chat"

    async def test_create_on_nonexistent_assistant_fails(self, client, auth_headers):
        fake_id = uuid.uuid4()
        response = await client.post(
            f"/assistants/{fake_id}/conversations",
            json={"title": "Ghost chat"},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestSendMessage:
    async def test_send_message_calls_llm_and_saves_response(
        self, client, auth_headers, test_assistant, test_conversation
    ):
        await client.patch(f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}", json={"use_rag": False}, headers=auth_headers)
        fake_llm_response = {
            "content": "This is a mock response from the LLM.",
            "tokens_input": 23,
            "tokens_output": 18,
            "model": "mock-model",
        }
        with (
            patch("app.services.conversation_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])),
            patch("app.services.conversation_service.chat", new=AsyncMock(return_value=fake_llm_response))
            ):
            response = await client.post(
                f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
                json={"content": "Hello there"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["message"]["content"] == "This is a mock response from the LLM."
        assert data["message"]["role"] == "assistant"
        assert data["tokens_used"] == 18

    async def test_llm_failure_rolls_back_and_returns_502(
        self, client, auth_headers, test_assistant, test_conversation
    ):
        await client.patch(f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}", json={"use_rag": False}, headers=auth_headers)
        with patch(
            "app.services.conversation_service.chat",
            new=AsyncMock(side_effect=LLMServiceError("timeout")),
        ) as mock_chat:
            response = await client.post(
                f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
                json={"content": "This message will fail"},
                headers=auth_headers,
            )

        mock_chat.assert_awaited_once()
        assert response.status_code == 502

        history_response = await client.get(
            f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            headers=auth_headers,
        )
        assert history_response.json() == []


class TestConversationOwnership:
    async def test_cannot_send_message_to_other_users_conversation(
        self, client, other_user_headers, test_assistant, test_conversation
    ):

        response = await client.post(
            f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            json={"content": "Hijack attempt"},
            headers=other_user_headers,
        )
        assert response.status_code == 404

    async def test_cannot_read_other_users_conversation_messages(
        self, client, other_user_headers, test_assistant, test_conversation
    ):
        response = await client.get(
            f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            headers=other_user_headers,
        )
        assert response.status_code == 404


async def test_rag_injects_relevant_context_into_system_prompt(
    client, auth_headers, test_assistant, test_conversation, test_document
):
    fake_chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=UUID(test_document["id"]),
        content="El horario de atención es de 9 a 18.",
        chunk_index=0,
        embedding=[0.1] * 1536,
    )
    fake_llm_response = {
        "content": "El horario es de 9 a 18hs. [S1]",
        "tokens_input": 10,
        "tokens_output": 10,
        "model": "test-model",
    }

    with (
        patch("app.services.conversation_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])),
        patch("app.services.conversation_service.search_relevant_chunks", new=AsyncMock(return_value=[fake_chunk])),
        patch("app.services.conversation_service.chat", new=AsyncMock(return_value=fake_llm_response)) as mock_chat,
    ):
        response = await client.post(
            f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            json={"content": "¿Cuál es el horario?"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    # Lo que importa: confirmar que el contenido del chunk llegó al system_prompt
    called_kwargs = mock_chat.call_args.kwargs
    assert "El horario de atención es de 9 a 18." in called_kwargs["messages"][-1]["content"]
    assert "untrusted data" in called_kwargs["system_prompt"]
    assert response.json()["message"]["sources"][0]["document_id"] == test_document["id"]

async def test_toggle_rag_mid_conversation(client, auth_headers, test_assistant, test_conversation):
    fake_llm_response = {"content": "ok", "tokens_input": 5, "tokens_output": 5, "model": "test-model"}

    with (
        patch("app.services.conversation_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])),
        patch("app.services.conversation_service.search_relevant_chunks", new=AsyncMock(return_value=[])),
        patch("app.services.conversation_service.chat", new=AsyncMock(return_value=fake_llm_response)),
    ):
        await client.post(
            f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            json={"content": "charla casual"}, headers=auth_headers,
        )

    patch_response = await client.patch(
        f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}",
        json={"use_rag": False}, headers=auth_headers,
    )
    assert patch_response.json()["use_rag"] is False

    with (
        patch("app.services.conversation_service.embed", new=AsyncMock()) as mock_embed,
        patch("app.services.conversation_service.chat", new=AsyncMock(return_value=fake_llm_response)),
    ):
        await client.post(
            f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            json={"content": "otro mensaje"}, headers=auth_headers,
        )
    mock_embed.assert_not_called()  # confirma que, tras el PATCH, dejó de buscar


async def test_cannot_update_other_users_conversation(client, other_user_headers, test_assistant, test_conversation):
    response = await client.patch(
        f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}",
        json={"use_rag": False}, headers=other_user_headers,
    )
    assert response.status_code == 404

async def test_rag_no_evidence_abstains_without_generation(client, auth_headers, test_assistant, test_conversation):
    with (
        patch("app.services.conversation_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])),
        patch("app.services.conversation_service.chat", new=AsyncMock()) as chat,
    ):
        response = await client.post(f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            json={"content": "What do my documents say?"}, headers=auth_headers)
    assert response.status_code == 200
    assert "couldn't find" in response.json()["message"]["content"]
    assert response.json()["message"]["sources"] == []
    chat.assert_not_awaited()


async def test_rag_unknown_citation_is_not_saved_as_supported_answer(client, auth_headers, test_assistant, test_conversation, test_document):
    with (
        patch("app.services.conversation_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])),
        patch("app.services.conversation_service.chat", new=AsyncMock(return_value={
            "content": "unsupported claim [S999]", "tokens_output": 4, "model": "fake"})),
    ):
        response = await client.post(f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            json={"content": "question"}, headers=auth_headers)
    assert response.status_code == 200
    assert "unsupported claim" not in response.json()["message"]["content"]
    assert response.json()["message"]["sources"] == []


async def test_null_rag_and_oversized_message_are_validation_errors(client, auth_headers, test_assistant, test_conversation):
    from app.core.config import settings
    path = f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}"
    assert (await client.patch(path, json={"use_rag": None}, headers=auth_headers)).status_code == 422
    assert (await client.post(path + "/messages", json={"content": "x" * (settings.MAX_MESSAGE_CHARS + 1)}, headers=auth_headers)).status_code == 422
