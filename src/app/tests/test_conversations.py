import uuid
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from app.core.exceptions import LLMServiceError


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
        with patch(
            "app.services.conversation_service.chat",
            new=AsyncMock(side_effect=LLMServiceError("timeout")),
        ):
            response = await client.post(
                f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
                json={"content": "This message will fail"},
                headers=auth_headers,
            )

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

from app.models.document import DocumentChunk

async def test_rag_injects_relevant_context_into_system_prompt(
    client, auth_headers, test_assistant, test_conversation
):
    fake_chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content="El horario de atención es de 9 a 18.",
        chunk_index=0,
        embedding=[0.1] * 1536,
    )
    fake_llm_response = {
        "content": "El horario es de 9 a 18hs.",
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
    assert "El horario de atención es de 9 a 18." in called_kwargs["system_prompt"]