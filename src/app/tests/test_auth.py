from unittest.mock import AsyncMock, patch
from uuid import UUID

from app.core.exceptions import ServiceUnavailableError
from app.models.user import User


class TestRegister:
    async def test_register_success(self, client):
        response = await client.post(
            "/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "ValidPass1234",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert "password" not in data  # nunca se devuelve el hash

    async def test_register_duplicate_email_fails(self, client, test_user):
        response = await client.post(
            "/auth/register",
            json={
                "email": test_user["email"],
                "password": "AnotherPass1234",
                "full_name": "Duplicate",
            },
        )
        assert response.status_code == 409


class TestLogin:
    async def test_login_success(self, client, test_user):
        response = await client.post(
            "/auth/login",
            data={
                "username": test_user["email"],
                "password": test_user["password"],
            },
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    async def test_login_wrong_password_fails(self, client, test_user):
        response = await client.post(
            "/auth/login",
            data={
                "username": test_user["email"],
                "password": "WrongPassword",
            },
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user_fails(self, client):
        response = await client.post(
            "/auth/login",
            data={
                "username": "ghost@test.com",
                "password": "Whatever123",
            },
        )
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


async def test_refresh_cookie_and_body_return_usable_tokens(client, test_user):
    login = await client.post('/auth/login', data={
        'username': test_user['email'], 'password': test_user['password']})
    for body in ({}, {'refresh_token': login.json()['refresh_token']}):
        response = await client.post('/auth/refresh', json=body)
        assert response.status_code == 200
        token = response.json()['access_token']
        assert isinstance(token, str)
        assert response.cookies['access_token'] == token
        protected = await client.get('/assistants', headers={'Authorization': f'Bearer {token}'})
        assert protected.status_code == 200


async def test_refresh_rejects_invalid_and_inactive_user(client, test_user, db_session):
    login = await client.post('/auth/login', data={
        'username': test_user['email'], 'password': test_user['password']})
    invalid = await client.post('/auth/refresh', json={'refresh_token': 'invalid'})
    assert invalid.status_code == 401
    wrong_type = await client.post('/auth/refresh', json={'refresh_token': login.json()['access_token']})
    assert wrong_type.status_code == 401
    user = await db_session.get(User, UUID(test_user['id']))
    user.is_active = False
    await db_session.commit()
    response = await client.post('/auth/refresh', json={'refresh_token': login.json()['refresh_token']})
    assert response.status_code == 403


async def test_logout_revokes_access_and_refresh(client, test_user):
    login = await client.post('/auth/login', data={
        'username': test_user['email'], 'password': test_user['password']})
    tokens = login.json()
    headers = {'Authorization': f"Bearer {tokens['access_token']}"}
    response = await client.post('/auth/logout', headers=headers)
    assert response.status_code == 204
    assert (await client.get('/assistants', headers=headers)).status_code == 401
    response = await client.post('/auth/refresh', json={'refresh_token': tokens['refresh_token']})
    assert response.status_code == 401


async def test_auth_outage_is_503(client, test_user):
    with patch('app.core.security.get_redis_client', new=AsyncMock(
        side_effect=ServiceUnavailableError('Temporarily unavailable'))):
        response = await client.post('/auth/login', data={
            'username': test_user['email'], 'password': test_user['password']})
    assert response.status_code == 503
