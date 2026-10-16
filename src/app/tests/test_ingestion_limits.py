from io import BytesIO
from unittest.mock import patch

import pytest
from pypdf import PdfWriter

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services.document_processing import (
    TextPage,
    chunk_pages,
    chunk_text,
    extract_pages,
    validate_file,
)


@pytest.mark.parametrize("filename, content", [("binary.txt", b"\xff"), ("binary.txt", b"\x00"),
    ("empty.txt", b" "), ("empty.txt", b""), ("data.exe", b"text"), ("bad.pdf", b"fake"),
    ("bad\rname.txt", b"text")])
def test_invalid_file_content_is_rejected(filename, content):
    with pytest.raises(ValidationError):
        validate_file(filename, content)


def test_empty_pdf_reports_ocr_requirement():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(ValidationError, match="OCR"):
        extract_pages("scan.pdf", stream.getvalue())


def test_limits_and_page_references(monkeypatch):
    monkeypatch.setattr(settings, "MAX_EXTRACTED_CHARS", 3)
    with pytest.raises(ValidationError, match="text limit"):
        extract_pages("notes.txt", b"long text")
    chunks = chunk_pages([TextPage("page one", 1), TextPage("page two", 2)])
    assert [(c.page_start, c.page_end) for c in chunks] == [(1, 1), (2, 2)]
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=10, overlap=10)


async def test_broker_failure_preserves_accepted_document(client, auth_headers, test_assistant):
    with patch("app.api.documents.process_document_task.delay", side_effect=ConnectionError):
        response = await client.post(f"/assistants/{test_assistant['id']}/documents",
            files={"file": ("notes.txt", b"text", "text/plain")}, headers=auth_headers)
    assert response.status_code == 202
    status = await client.get(f"/assistants/{test_assistant['id']}/documents/{response.json()['id']}", headers=auth_headers)
    assert status.json()["status"] == "pending"


async def test_streaming_upload_limit_without_content_length(client, auth_headers, test_assistant, monkeypatch):
    monkeypatch.setattr(settings, "MAX_DOCUMENT_SIZE_MB", 1)
    async def body():
        yield b'--testboundary\r\nContent-Disposition: form-data; name="file"; filename="big.txt"\r\nContent-Type: text/plain\r\n\r\n'
        for _ in range(20):
            yield b"x" * 65536
        yield b"\r\n--testboundary--\r\n"
    response = await client.post(f"/assistants/{test_assistant['id']}/documents", content=body(),
        headers={**auth_headers, "Content-Type": "multipart/form-data; boundary=testboundary"})
    assert response.status_code == 413


async def test_retry_endpoint_is_owned_and_dispatches(client, auth_headers, other_user_headers, test_assistant, test_document):
    path = f"/assistants/{test_assistant['id']}/documents/{test_document['id']}/retry"
    assert (await client.post(path, headers=other_user_headers)).status_code == 404
    with patch("app.api.documents.process_document_task.delay") as publish:
        response = await client.post(path, headers=auth_headers)
    assert response.status_code == 202
    assert response.json()["status"] == "pending"
    publish.assert_called_once()
