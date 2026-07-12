import uuid
import pytest_asyncio


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
    async def test_send_message_returns_mock_response(
        self, client, auth_headers, test_assistant, test_conversation
    ):
        response = await client.post(
            f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            json={"content": "Hello there"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "Hello there" in data["message"]["content"]
        assert data["message"]["role"] == "assistant"

    async def test_history_persists_both_messages_in_order(
        self, client, auth_headers, test_assistant, test_conversation
    ):
        await client.post(
            f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            json={"content": "Hola"},
            headers=auth_headers,
        )

        response = await client.get(
            f"/assistants/{test_assistant['id']}/conversations/{test_conversation['id']}/messages",
            headers=auth_headers,
        )
        messages = response.json()

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hola"
        assert messages[1]["role"] == "assistant"


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
