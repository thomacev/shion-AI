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
        with patch("app.services.conversation_service.chat", new=AsyncMock(return_value=fake_llm_response)):
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
        """Caso clave: el atacante NO tiene el assistant_id correcto porque
        no es dueño de ningún asistente propio con ese ID. Simulamos el caso
        más peligroso: intenta usar el assistant_id ajeno directamente."""
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
