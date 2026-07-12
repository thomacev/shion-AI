from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant
from app.schemas.assistant_schema import AssistantCreateSchema, AssistantUpdateSchema
from app.core.exceptions import ResourceNotFoundError


async def create_assistant(
    user_id: UUID,
    data: AssistantCreateSchema,
    db: AsyncSession,
) -> Assistant:
    assistant = Assistant(
        user_id=user_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
    )
    db.add(assistant)
    await db.commit()
    await db.refresh(assistant)
    return assistant


async def list_assistants(
    user_id: UUID,
    db: AsyncSession,
) -> list[Assistant]:
    stmt = select(Assistant).where(Assistant.user_id == user_id, Assistant.is_active)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_assistant(
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> Assistant:
    return await _get_assistant_for_user(assistant_id, user_id, db)


async def update_assistant(
    assistant_id: UUID,
    user_id: UUID,
    data: AssistantUpdateSchema,
    db: AsyncSession,
) -> Assistant:
    assistant = await _get_assistant_for_user(assistant_id, user_id, db)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(assistant, field, value)

    await db.commit()
    await db.refresh(assistant)
    return assistant


async def delete_assistant(
    assistant_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> None:
    assistant = await _get_assistant_for_user(assistant_id, user_id, db)
    assistant.is_active = False
    await db.commit()


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
