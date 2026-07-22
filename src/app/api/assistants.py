from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.core.dependencies import get_db, get_current_user
from app.schemas.assistant_schema import (
    AssistantCreateSchema,
    AssistantUpdateSchema,
    AssistantResponseSchema,
)
from app.services import assistant_service
from app.core.rate_limit import limiter

router = APIRouter(prefix="/assistants", tags=["assistants"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AssistantResponseSchema,
)
@limiter.limit("20/hour")
async def create_assistant(
    request: Request,
    data: AssistantCreateSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await assistant_service.create_assistant(
        user_id=current_user["id"],
        data=data,
        db=db,
    )


@router.get(
    "",
    response_model=list[AssistantResponseSchema],
)
async def list_assistants(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await assistant_service.list_assistants(
        user_id=current_user["id"],
        db=db,
    )


@router.get(
    "/{assistant_id}",
    response_model=AssistantResponseSchema,
)
async def get_assistant(
    assistant_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await assistant_service.get_assistant(
        assistant_id=assistant_id,
        user_id=current_user["id"],
        db=db,
    )


@router.patch(
    "/{assistant_id}",
    response_model=AssistantResponseSchema,
)
async def update_assistant(
    assistant_id: UUID,
    data: AssistantUpdateSchema,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await assistant_service.update_assistant(
        assistant_id=assistant_id,
        user_id=current_user["id"],
        data=data,
        db=db,
    )


@router.delete(
    "/{assistant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_assistant(
    assistant_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await assistant_service.delete_assistant(
        assistant_id=assistant_id,
        user_id=current_user["id"],
        db=db,
    )
