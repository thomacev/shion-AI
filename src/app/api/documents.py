from uuid import UUID
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.schemas.document_schema import DocumentResponseSchema
from app.services import document_service

router = APIRouter(prefix="/assistants/{assistant_id}/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentResponseSchema)
async def upload_document(
    assistant_id: UUID,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    return await document_service.process_document(
        assistant_id=assistant_id,
        user_id=current_user["id"],
        filename=file.filename,
        content=content,
        db=db,
    )