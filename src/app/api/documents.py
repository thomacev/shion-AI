from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings


from app.core.dependencies import get_db, get_current_user
from app.schemas.document_schema import DocumentResponseSchema
from app.services import document_service
from app.services.document_service import MAX_DOCUMENT_SIZE_BYTES

import base64
from app.tasks.document_tasks import process_document_task

router = APIRouter(prefix="/assistants/{assistant_id}/documents", tags=["documents"])



#nuevo
@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponseSchema)
async def upload_document(
    request: Request,
    assistant_id: UUID,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    content = await file.read()

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum allowed size of {settings.MAX_DOCUMENT_SIZE_MB}MB",
        )
    
    document = await document_service.create_pending_document(
        assistant_id=assistant_id,
        user_id=current_user["id"],
        filename=file.filename,
        content_size=len(content),
        db=db,
    )
    process_document_task.delay(
        str(document.id), file.filename, base64.b64encode(content).decode("ascii")
    )
    return document


@router.get("", response_model=list[DocumentResponseSchema])
async def list_documents(
    assistant_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.list_documents(assistant_id, current_user["id"], db, limit, offset)
@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    assistant_id: UUID,
    document_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await document_service.delete_document(document_id, assistant_id, current_user["id"], db)


@router.get("/{document_id}", response_model=DocumentResponseSchema)
async def get_document(
    assistant_id: UUID,
    document_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await document_service.get_document(document_id, assistant_id, current_user["id"], db)