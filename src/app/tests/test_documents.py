from unittest.mock import AsyncMock, patch
import uuid
from app.core.exceptions import LLMServiceError

class TestUploadDocument:
    async def test_upload_document_processes_and_creates_chunks(
        self, client, auth_headers, test_assistant
    ):
        fake_embeddings = [[0.1] * 1536, [0.2] * 1536]
        with patch("app.services.document_service.embed", new=AsyncMock(return_value=fake_embeddings)):
            response = await client.post(
                f"/assistants/{test_assistant['id']}/documents",
                files={"file": ("notes.txt", b"contenido de prueba " * 100, "text/plain")},
                headers=auth_headers,
            )
        assert response.status_code == 201
        assert response.json()["status"] == "ready"

    async def test_upload_failure_marks_document_as_failed(
        self, client, auth_headers, test_assistant
    ):
        with patch("app.services.document_service.embed", new=AsyncMock(side_effect=LLMServiceError("failed"))):
            response = await client.post(
                f"/assistants/{test_assistant['id']}/documents",
                files={"file": ("notes.txt", b"contenido", "text/plain")},
                headers=auth_headers,
            )
        assert response.status_code == 201
        assert response.json()["status"] == "failed"

    async def test_cannot_upload_to_other_users_assistant(
        self, client, other_user_headers, test_assistant
    ):
        response = await client.post(
            f"/assistants/{test_assistant['id']}/documents",
            files={"file": ("notes.txt", b"contenido", "text/plain")},
            headers=other_user_headers,
        )
        assert response.status_code == 404


class TestListDocuments:
    async def test_list_only_returns_own_assistant_documents(
        self, client, auth_headers, other_user_headers, test_assistant, test_document
    ):
        response = await client.get(
            f"/assistants/{test_assistant['id']}/documents", headers=auth_headers
        )
        assert len(response.json()) == 1

        response_other = await client.get(
            f"/assistants/{test_assistant['id']}/documents", headers=other_user_headers
        )
        assert response_other.status_code == 404  


class TestDeleteDocument:
    async def test_delete_removes_document_and_its_chunks(
        self, client, auth_headers, test_assistant, test_document
    ):
        response = await client.delete(
            f"/assistants/{test_assistant['id']}/documents/{test_document['id']}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        list_response = await client.get(
            f"/assistants/{test_assistant['id']}/documents", headers=auth_headers
        )
        assert list_response.json() == []

    async def test_cannot_delete_other_users_document(
        self, client, other_user_headers, test_assistant, test_document
    ):
        response = await client.delete(
            f"/assistants/{test_assistant['id']}/documents/{test_document['id']}",
            headers=other_user_headers,
        )
        assert response.status_code == 404

    async def test_delete_nonexistent_document_returns_404(
        self, client, auth_headers, test_assistant
    ):
        fake_id = uuid.uuid4()
        response = await client.delete(
            f"/assistants/{test_assistant['id']}/documents/{fake_id}",
            headers=auth_headers,
        )
        assert response.status_code == 404