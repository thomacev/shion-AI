
class TestRegister:
    async def test_register_success(self, client):
        response = await client.post("/auth/register", json={
            "email": "newuser@test.com",
            "password": "ValidPass1234",
            "full_name": "New User",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert "password" not in data  # nunca se devuelve el hash

    async def test_register_duplicate_email_fails(self, client, test_user):
        response = await client.post("/auth/register", json={
            "email": test_user["email"],
            "password": "AnotherPass1234",
            "full_name": "Duplicate",
        })
        assert response.status_code == 409


class TestLogin:
    async def test_login_success(self, client, test_user):
        response = await client.post("/auth/login", data={
            "username": test_user["email"],
            "password": test_user["password"],
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_login_wrong_password_fails(self, client, test_user):
        response = await client.post("/auth/login", data={
            "username": test_user["email"],
            "password": "WrongPassword",
        })
        assert response.status_code == 401

    async def test_login_nonexistent_user_fails(self, client):
        response = await client.post("/auth/login", data={
            "username": "ghost@test.com",
            "password": "Whatever123",
        })
        assert response.status_code == 401


class TestProtectedRoutes:
    async def test_no_token_rejected(self, client):
        response = await client.get("/assistants")
        assert response.status_code == 401

    async def test_invalid_token_rejected(self, client):
        response = await client.get(
            "/assistants",
            headers={"Authorization": "Bearer garbage.token.here"},
        )
        assert response.status_code == 401