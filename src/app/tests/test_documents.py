from unittest.mock import AsyncMock, patch
import uuid
from app.core.exceptions import LLMServiceError
from app.core.config import settings

class TestUploadDocument:
    async def test_upload_dispatches_processing_task(self, client, auth_headers, test_assistant):
        with patch("app.api.documents.process_document_task.delay") as mock_delay:
            response = await client.post(
                f"/assistants/{test_assistant['id']}/documents",
                files={"file": ("notes.txt", b"contenido de prueba", "text/plain")},
                headers=auth_headers,
            )
        assert response.status_code == 202
        assert response.json()["status"] == "pending"
        mock_delay.assert_called_once()

    async def test_cannot_upload_to_other_users_assistant(self, client, other_user_headers, test_assistant):
        with patch("app.api.documents.process_document_task.delay"):
            response = await client.post(
                f"/assistants/{test_assistant['id']}/documents",
                files={"file": ("notes.txt", b"contenido", "text/plain")},
                headers=other_user_headers,
            )
        assert response.status_code == 404

    async def test_cannot_upload_to_other_users_assistant(self, client, other_user_headers, test_assistant):
            with patch("app.api.documents.process_document_task.delay"):
                response = await client.post(
                    f"/assistants/{test_assistant['id']}/documents",
                    files={"file": ("notes.txt", b"contenido", "text/plain")},
                    headers=other_user_headers,
                )
            assert response.status_code == 404

    async def test_upload_rejects_file_over_size_limit(self,client, auth_headers, test_assistant):
        huge_content = b"x" * (settings.MAX_DOCUMENT_SIZE_MB * 1024 * 1024 + 1)
        response = await client.post(
            f"/assistants/{test_assistant['id']}/documents",
            files={"file": ("big.txt", huge_content, "text/plain")},
            headers=auth_headers,
        )
        assert response.status_code == 413


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


class TestGetDocument:
    async def test_get_document_returns_current_status(
        self, client, auth_headers, test_assistant, test_document
    ):
        response = await client.get(
            f"/assistants/{test_assistant['id']}/documents/{test_document['id']}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == test_document["id"]

    async def test_cannot_get_other_users_document(
        self, client, other_user_headers, test_assistant, test_document
    ):
        response = await client.get(
            f"/assistants/{test_assistant['id']}/documents/{test_document['id']}",
            headers=other_user_headers,
        )
        assert response.status_code == 404

async def test_download_document_returns_original_file(client, auth_headers, test_assistant, test_document):
    response = await client.get(
        f"/assistants/{test_assistant['id']}/documents/{test_document['id']}/file",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.content == b"El horario de atencion es de 9 a 18."
    assert response.headers["content-type"] == "text/plain; charset=utf-8"


async def test_cannot_download_other_users_document(client, other_user_headers, test_assistant, test_document):
    response = await client.get(
        f"/assistants/{test_assistant['id']}/documents/{test_document['id']}/file",
        headers=other_user_headers,
    )
    assert response.status_code == 404