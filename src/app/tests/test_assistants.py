import uuid


class TestCreateAssistant:
    async def test_create_success(self, client, auth_headers):
        response = await client.post(
            "/assistants",
            json={"name": "Legal Bot", "system_prompt": "You are a lawyer."},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Legal Bot"
        assert data["is_active"] is True

    async def test_create_uses_default_system_prompt(self, client, auth_headers):
        response = await client.post(
            "/assistants",
            json={"name": "No Prompt Bot"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        assert response.json()["system_prompt"] == "You are a helpful assistant."

    async def test_create_without_token_rejected(self, client):
        response = await client.post("/assistants", json={"name": "Ghost"})
        assert response.status_code == 401


class TestListAssistants:
    async def test_list_only_returns_own_assistants(
        self, client, auth_headers, other_user_headers
    ):
        await client.post("/assistants", json={"name": "Mine"}, headers=auth_headers)
        await client.post(
            "/assistants", json={"name": "Theirs"}, headers=other_user_headers
        )

        response = await client.get("/assistants", headers=auth_headers)
        names = [a["name"] for a in response.json()]

        assert "Mine" in names
        assert "Theirs" not in names

    async def test_list_excludes_deleted(self, client, auth_headers, test_assistant):
        await client.delete(f"/assistants/{test_assistant['id']}", headers=auth_headers)
        response = await client.get("/assistants", headers=auth_headers)
        ids = [a["id"] for a in response.json()]
        assert test_assistant["id"] not in ids


class TestUpdateAssistant:
    async def test_partial_update_only_changes_given_fields(
        self, client, auth_headers, test_assistant
    ):
        response = await client.patch(
            f"/assistants/{test_assistant['id']}",
            json={"name": "Renamed"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Renamed"
        # el system_prompt no debería haberse tocado
        assert data["system_prompt"] == test_assistant["system_prompt"]


class TestOwnership:
    """Estos son los tests que más importan: verifican que un usuario
    no puede leer, modificar ni borrar recursos de otro usuario."""

    async def test_cannot_get_other_users_assistant(
        self, client, other_user_headers, test_assistant
    ):
        response = await client.get(
            f"/assistants/{test_assistant['id']}", headers=other_user_headers
        )
        assert response.status_code == 404  # no 403 — no revelamos que existe

    async def test_cannot_update_other_users_assistant(
        self, client, other_user_headers, test_assistant
    ):
        response = await client.patch(
            f"/assistants/{test_assistant['id']}",
            json={"name": "Hijacked"},
            headers=other_user_headers,
        )
        assert response.status_code == 404

    async def test_cannot_delete_other_users_assistant(
        self, client, other_user_headers, test_assistant
    ):
        response = await client.delete(
            f"/assistants/{test_assistant['id']}", headers=other_user_headers
        )
        assert response.status_code == 404

    async def test_nonexistent_assistant_returns_404(self, client, auth_headers):
        fake_id = uuid.uuid4()
        response = await client.get(f"/assistants/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
