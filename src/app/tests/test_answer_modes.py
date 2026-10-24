import json
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core.exceptions import LLMServiceError
from app.models.document import DocumentChunk


async def create_hybrid(client, headers, assistant):
    response = await client.post(
        f"/assistants/{assistant['id']}/conversations",
        json={"title": "Combined answers", "allow_general_knowledge": True},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["allow_general_knowledge"] is True
    return f"/assistants/{assistant['id']}/conversations/{response.json()['id']}"


def model_response(document="", general=""):
    return {"content": json.dumps({"document_answer": document, "general_answer": general}),
            "tokens_output": 20, "model": "test-model"}


async def test_hybrid_without_documents_generates_and_persists_general_answer(client, auth_headers, test_assistant):
    path = await create_hybrid(client, auth_headers, test_assistant)
    with (
        patch("app.services.conversation_service.embed", new=AsyncMock()) as embed,
        patch("app.services.conversation_service.chat", new=AsyncMock(
            return_value=model_response(general="An embedding represents meaning as numbers."))) as chat,
    ):
        response = await client.post(path + "/messages", json={"content": "What is an embedding?"}, headers=auth_headers)
    assert response.status_code == 200
    message = response.json()["message"]
    assert message["answer_basis"] == "general_knowledge"
    assert message["sources"] == []
    assert "General knowledge · no web search" in message["content"]
    embed.assert_not_awaited()
    assert json.loads(chat.call_args.kwargs["messages"][-1]["content"])["sources"] == []
    assert "response_schema" in chat.call_args.kwargs
    assert "No internet search" in chat.call_args.kwargs["system_prompt"]
    history = (await client.get(path + "/messages", headers=auth_headers)).json()
    assert history[-1] == message
    assert history[0]["answer_basis"] is None


@pytest.mark.parametrize(
    "document_text,general_text,basis",
    [("Support is available 9–18. [S1]", "", "documents"),
     ("Support is available 9–18. [S1]", "A support window defines when a team responds.", "mixed"),
     ("", "An embedding represents meaning as numbers.", "general_knowledge"),
     ("", "", "insufficient_evidence")],
)
async def test_hybrid_sections_have_correct_persisted_provenance(
    client, auth_headers, test_assistant, test_document, document_text, general_text, basis,
):
    path = await create_hybrid(client, auth_headers, test_assistant)
    chunk = DocumentChunk(document_id=UUID(test_document["id"]), chunk_index=0,
                          content="Support hours are 9–18.", page_start=2, page_end=2)
    with (
        patch("app.services.conversation_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])),
        patch("app.services.conversation_service.search_relevant_chunks", new=AsyncMock(return_value=[chunk])),
        patch("app.services.conversation_service.chat", new=AsyncMock(
            return_value=model_response(document_text, general_text))) as chat,
    ):
        response = await client.post(path + "/messages", json={"content": "Explain support hours."}, headers=auth_headers)
    assert response.status_code == 200
    answer = response.json()["message"]
    assert answer["answer_basis"] == basis
    assert len(answer["sources"]) == (1 if document_text else 0)
    if document_text:
        assert answer["sources"][0]["document_id"] == test_document["id"]
        assert answer["sources"][0]["page_start"] == 2
        assert "From your documents" in answer["content"]
    request = json.loads(chat.call_args.kwargs["messages"][-1]["content"])
    assert request["sources"][0]["text"] == chunk.content
    assert "untrusted data" in chat.call_args.kwargs["system_prompt"]
    # Changing mode must not re-label earlier messages.
    changed = await client.patch(path, json={"allow_general_knowledge": False}, headers=auth_headers)
    assert changed.status_code == 200
    assert changed.json()["allow_general_knowledge"] is False
    history = (await client.get(path + "/messages", headers=auth_headers)).json()
    assert history[-1]["answer_basis"] == basis


async def test_no_retrieval_match_uses_general_knowledge_but_retrieval_failure_does_not(
    client, auth_headers, test_assistant, test_document,
):
    path = await create_hybrid(client, auth_headers, test_assistant)
    with (
        patch("app.services.conversation_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])),
        patch("app.services.conversation_service.search_relevant_chunks", new=AsyncMock(return_value=[])),
        patch("app.services.conversation_service.chat", new=AsyncMock(
            return_value=model_response(general="An embedding is a numeric representation."))),
    ):
        response = await client.post(path + "/messages", json={"content": "What is an embedding?"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["message"]["answer_basis"] == "general_knowledge"
    with (
        patch("app.services.conversation_service.embed", new=AsyncMock(side_effect=LLMServiceError("Embedding unavailable"))),
        patch("app.services.conversation_service.chat", new=AsyncMock()) as chat,
    ):
        response = await client.post(path + "/messages", json={"content": "Try again."}, headers=auth_headers)
    assert response.status_code == 502
    chat.assert_not_awaited()
    assert len((await client.get(path + "/messages", headers=auth_headers)).json()) == 2


@pytest.mark.parametrize("content", [
    "not JSON",
    '{"document_answer": "Invented private fact [S999]", "general_answer": ""}',
    '{"document_answer": "Missing citation", "general_answer": ""}',
    '{"document_answer": "", "general_answer": "Falsely attributed [S1]"}',
    '{"document_answer": "", "general_answer": "Answer", "answer_basis": "internet"}',
])
async def test_invalid_provenance_is_rejected_without_saving_and_claim_is_released(
    client, auth_headers, test_assistant, test_document, content,
):
    path = await create_hybrid(client, auth_headers, test_assistant)
    chunk = DocumentChunk(document_id=UUID(test_document["id"]), chunk_index=0, content="Known fact.")
    with (
        patch("app.services.conversation_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])),
        patch("app.services.conversation_service.search_relevant_chunks", new=AsyncMock(return_value=[chunk])),
        patch("app.services.conversation_service.chat", new=AsyncMock(
            return_value={"content": content, "tokens_output": 10, "model": "test-model"},
        )),
    ):
        response = await client.post(path + "/messages", json={"content": "question"}, headers=auth_headers)
    assert response.status_code == 502
    assert (await client.get(path + "/messages", headers=auth_headers)).json() == []
    with (
        patch("app.services.conversation_service.embed", new=AsyncMock(return_value=[[0.1] * 1536])),
        patch("app.services.conversation_service.search_relevant_chunks", new=AsyncMock(return_value=[])),
        patch("app.services.conversation_service.chat", new=AsyncMock(
            return_value=model_response(general="A valid answer."),
        )),
    ):
        response = await client.post(path + "/messages", json={"content": "question"}, headers=auth_headers)
    assert response.status_code == 200


async def test_mode_defaults_validation_and_ownership(client, auth_headers, other_user_headers, test_assistant):
    base = f"/assistants/{test_assistant['id']}/conversations"
    response = await client.post(base, json={}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["allow_general_knowledge"] is False
    path = base + "/" + response.json()["id"]
    assert (await client.patch(path, json={"allow_general_knowledge": None}, headers=auth_headers)).status_code == 422
    assert (await client.post(base, json={"allow_general_knowledge": None}, headers=auth_headers)).status_code == 422
    assert (await client.patch(path, json={"allow_general_knowledge": True}, headers=other_user_headers)).status_code == 404


async def test_no_documents_cannot_be_labelled_as_document_evidence(client, auth_headers, test_assistant):
    path = await create_hybrid(client, auth_headers, test_assistant)
    with patch("app.services.conversation_service.chat", new=AsyncMock(
        return_value=model_response(document="A fabricated document claim. [S1]"),
    )):
        response = await client.post(path + "/messages", json={"content": "What do my files say?"}, headers=auth_headers)
    assert response.status_code == 502
    assert (await client.get(path + "/messages", headers=auth_headers)).json() == []
