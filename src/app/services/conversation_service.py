from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message, MessageRole
from app.models.document import DocumentChunk
from app.schemas.conversation_schema import ConversationCreateSchema, ConversationUpdateSchema
from app.core.exceptions import ResourceNotFoundError

from app.services.llm_service import chat
from app.services.embedding_service import embed
from app.services.document_service import search_relevant_chunks
from app.services.assistant_service import _get_assistant_for_user
from app.core.logger import logger



def build_system_prompt(base_prompt: str, context_chunks: list[DocumentChunk]) -> str:
    if not context_chunks:
        return base_prompt
    context_text = "\n\n".join(chunk.content for chunk in context_chunks)
    return f"{base_prompt}\n\nRelevant context for the assistant:\n{context_text}"

async def _get_recent_history(
    conversation_id: UUID,
    exclude_message_id: UUID,
    db: AsyncSession,
    limit: int = 20,
) -> list[dict]:
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.id != exclude_message_id,
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    recent_messages = list(result.scalars().all())
    return [
        {"role": message.role.value, "content": message.content}
        for message in reversed(recent_messages)
    ]

async def create_conversation(
    assistant_id: UUID,
    user_id: UUID,
    data: ConversationCreateSchema,
    db: AsyncSession,
) -> Conversation:
    await _get_assistant_for_user(assistant_id, user_id, db)

    conversation = Conversation(
        assistant_id=assistant_id,
        title=data.title,
        use_rag=data.use_rag
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)

    logger.info(
        "Conversation created successfully",
        extra={
            "conversation_id": str(conversation.id),
            "assistant_id": str(assistant_id),
            "user_id": str(user_id),
        },
    )
    return conversation

async def update_conversation(
    conversation_id: UUID,
    assistant_id: UUID,
    user_id: UUID,
    data: ConversationUpdateSchema,
    db: AsyncSession,
) -> Conversation:
    await _get_assistant_for_user(assistant_id, user_id, db)
    conversation = await _get_conversation_for_assistant(conversation_id, assistant_id, db)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conversation, field, value)

    await db.commit()
    await db.refresh(conversation)

    logger.info(
        "Conversation updated successfully",
        extra={
            "conversation_id": str(conversation_id),
            "assistant_id": str(assistant_id),
            "user_id": str(user_id),
            "updated_fields": list(update_data.keys()),
        },
    )
    return conversation

async def send_message(
    assistant_id: UUID,
    conversation_id: UUID,
    user_id: UUID,
    content: str,
    db: AsyncSession,
) -> dict:
    assistant = await _get_assistant_for_user(assistant_id, user_id, db)
    conversation = await _get_conversation_for_assistant(conversation_id, assistant_id, db)

    logger.info(
        "Processing user message for conversation",
        extra={
            "conversation_id": str(conversation_id),
            "assistant_id": str(assistant_id),
            "user_id": str(user_id),
            "use_rag": conversation.use_rag,
        },
    )

    user_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=content,
    )
    db.add(user_message)
    await db.flush()

    history = await _get_recent_history(conversation_id, user_message.id, db)
    history.append({"role": "user", "content": content})

    if conversation.use_rag:
        [query_embedding] = await embed([content], task_type="RETRIEVAL_QUERY")
        relevant_chunks = await search_relevant_chunks(assistant_id, query_embedding, db)
        logger.info(
            "Retrieved context chunks for message",
            extra={
                "conversation_id": str(conversation_id),
                "chunks_found": len(relevant_chunks),
            },
        )
    else:
        relevant_chunks = []
        logger.info(
            "RAG context retrieval skipped for conversation",
            extra={
                "conversation_id": str(conversation_id),
                "use_rag": False,
            },
        )

    system_prompt = build_system_prompt(assistant.system_prompt, relevant_chunks)
    llm_response = await chat(system_prompt=system_prompt, messages=history)

    assistant_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=llm_response["content"],
        tokens_used=llm_response["tokens_output"],
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    logger.info(
        "Message sent and assistant response generated",
        extra={
            "conversation_id": str(conversation_id),
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id),
            "tokens_used": llm_response["tokens_output"],
            "model": llm_response["model"],
            "use_rag": conversation.use_rag,
        },
    )

    return {
        "message": assistant_message,
        "tokens_used": llm_response["tokens_output"],
        "model": llm_response["model"],
    }


async def list_conversations(
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[Conversation]:
    await _get_assistant_for_user(assistant_id, user_id, db)

    stmt = (
        select(Conversation)
        .where(Conversation.assistant_id == assistant_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_messages(
    conversation_id: UUID,
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[Message]:
    await _get_assistant_for_user(assistant_id, user_id, db)
    await _get_conversation_for_assistant(conversation_id, assistant_id, db)

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_conversation_for_assistant(
    conversation_id: UUID,
    assistant_id: UUID,
    db: AsyncSession,
) -> Conversation:
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.assistant_id == assistant_id,
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if not conversation:
        logger.warning(
                    "Conversation lookup failed: resource not found",
                    extra={
                        "conversation_id": str(conversation_id),
                        "assistant_id": str(assistant_id),
                    },
                )
        raise ResourceNotFoundError("Conversation not found")
    return conversation

