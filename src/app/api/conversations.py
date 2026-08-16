from uuid import UUID
from fastapi import APIRouter, Depends, status, Request, Query

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.schemas.conversation_schema import (
    ConversationCreateSchema,
    ConversationResponseSchema,
    MessageCreateSchema,
    MessageResponseSchema,
    ChatResponseSchema,
    ConversationUpdateSchema
)
from app.services import conversation_service
from app.core.rate_limit import limiter

router = APIRouter(
    prefix="/assistants/{assistant_id}/conversations", tags=["conversations"]
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationResponseSchema,
)
async def create_conversation(
    assistant_id: UUID,
    data: ConversationCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.create_conversation(
        assistant_id=assistant_id,
        user_id=current_user["id"],
        data=data,
        db=db,
    )


@router.get("", response_model=list[ConversationResponseSchema])
async def list_conversations(
    assistant_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.list_conversations(
        assistant_id=assistant_id, user_id=current_user["id"], db=db, limit=limit, offset=offset
    )

@router.post("/{conversation_id}/messages", response_model=ChatResponseSchema)
@limiter.limit("10/minute")
async def send_message(
    request: Request,
    assistant_id: UUID,
    conversation_id: UUID,
    data: MessageCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.send_message(
        assistant_id=assistant_id, conversation_id=conversation_id,
        user_id=current_user["id"], content=data.content, db=db,
    )

@router.get("/{conversation_id}/messages", response_model=list[MessageResponseSchema])
async def get_messages(
    assistant_id: UUID,
    conversation_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.get_messages(
        conversation_id=conversation_id, assistant_id=assistant_id, user_id=current_user["id"],
        db=db, limit=limit, offset=offset,
    )

@router.patch("/{conversation_id}", response_model=ConversationResponseSchema)
async def update_conversation(
    assistant_id: UUID,
    conversation_id: UUID,
    data: ConversationUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await conversation_service.update_conversation(
        conversation_id=conversation_id, assistant_id=assistant_id,
        user_id=current_user["id"], data=data, db=db,
    )
