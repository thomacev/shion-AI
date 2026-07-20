from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message, MessageRole
from app.models.assistant import Assistant
from app.schemas.conversation_schema import ConversationCreateSchema
from app.core.exceptions import ResourceNotFoundError
from app.services.llm_service import chat



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

    #this replace the mock, but my tests are gonna fail so far
    #there are other ways to do this, but for now I will keep it simple and just get the last 20 messages from the conversation
    stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.id != user_message.id,
            )
        .order_by(Message.created_at.desc())
        .limit(20)
    )

    result = await db.execute(stmt)
    recent_messages = list(result.scalars().all())

    history = [
        {"role": message.role.value, "content": message.content}
        for message in reversed(recent_messages)
    ]
    history.append({"role": "user", "content": content})
    llm_response = await chat(
        system_prompt=assistant.system_prompt,
        messages=history,)
    
    assistant_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=llm_response["content"],
        tokens_used=llm_response["tokens_output"],
    )
    db.add(assistant_message)
    await db.commit()
    await db.refresh(assistant_message)

    return {
        "message": assistant_message,
        "tokens_used": llm_response["tokens_output"],
        "model": llm_response["model"],
    }


async def list_conversations(
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> list[Conversation]:
    await _get_assistant_for_user(assistant_id, user_id, db)

    stmt = (
        select(Conversation)
        .where(Conversation.assistant_id == assistant_id)
        .order_by(Conversation.created_at.desc())
    )
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

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_assistant_for_user(
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Assistant:
    stmt = select(Assistant).where(
        Assistant.id == assistant_id, Assistant.user_id == user_id, Assistant.is_active
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
