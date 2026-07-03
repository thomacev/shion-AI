from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message, MessageRole
from app.models.assistant import Assistant
from app.schemas.conversation_schema import ConversationCreateSchema
from app.core.exceptions import ResourceNotFoundError


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
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def send_message(
    assistant_id: UUID,
    conversation_id: UUID,
    user_id: UUID,
    content: str,
    db: AsyncSession,
) -> dict:
    assistant = await _get_assistant_for_user(assistant_id, user_id, db)
    await _get_conversation_for_assistant(conversation_id, assistant_id, db)

    user_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=content,
    )
    db.add(user_message)
    await db.flush()

    # MOCK — despues se reemplaza con la llamada a la API de OpenRouter
    mock_response = f"[Mock] I got your message: '{content}'. I am {assistant.name}."

    assistant_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=mock_response,
        tokens_used=None,
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    return {
        "message": assistant_message,
        "tokens_used": None,
        "model": None,
    }


async def list_conversations(
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> list[Conversation]:
    await _get_assistant_for_user(assistant_id, user_id, db)

    stmt = select(Conversation).where(
        Conversation.assistant_id == assistant_id
    ).order_by(Conversation.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_messages(
    conversation_id: UUID,
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> list[Message]:
    await _get_assistant_for_user(assistant_id, user_id, db)
    await _get_conversation_for_assistant(conversation_id, assistant_id, db)

    stmt = select(Message).where(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_assistant_for_user(
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Assistant:
    stmt = select(Assistant).where(
        Assistant.id == assistant_id,
        Assistant.user_id == user_id,
        Assistant.is_active == True,
    )
    result = await db.execute(stmt)
    assistant = result.scalar_one_or_none()
    if not assistant:
        raise ResourceNotFoundError("Assistant not found")
    return assistant


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
        raise ResourceNotFoundError("Conversation not found")
    return conversation