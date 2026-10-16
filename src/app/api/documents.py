import asyncio
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import ResourceNotFoundError
from app.core.logger import logger
from app.schemas.document_schema import DocumentResponseSchema
from app.services import document_service
from app.services.document_service import MAX_DOCUMENT_SIZE_BYTES
from app.tasks.document_tasks import process_document_task

router = APIRouter(prefix="/assistants/{assistant_id}/documents", tags=["documents"])



@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponseSchema)
async def upload_document(
    request: Request,
    assistant_id: UUID,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read(MAX_DOCUMENT_SIZE_BYTES + 1)
    await file.close()
    if len(content) > MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_DOCUMENT_SIZE_MB}MB")

    document = await document_service.create_pending_document(
        assistant_id=assistant_id,
        user_id=current_user["id"],
        filename=file.filename or "",
        content=content,
        content_type=file.content_type,
        db=db,
    )
    await _dispatch_document(document.id)
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


@router.get("/{document_id}/file")
async def download_document_file(
    assistant_id: UUID,
    document_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await document_service.get_document(document_id, assistant_id, current_user["id"], db)
    if document.original_content is None:
        raise ResourceNotFoundError("Original file is not available for this document")
    return Response(
        content=document.original_content,
        media_type=document.content_type or "application/octet-stream",
        headers={"Content-Disposition": "attachment; filename*=UTF-8\'\'" + quote(document.filename, safe="")},
    )

async def _dispatch_document(document_id: UUID) -> None:
    try:
        await asyncio.to_thread(process_document_task.delay, str(document_id))
    except Exception as exc:  # noqa: BLE001 -- Keep the persisted upload available for recovery on any publication failure.
        # The durable pending row is recovered by the periodic scheduler.
        logger.warning("Document queued for recovery after dispatch failure", document_id=str(document_id),
                       error_type=type(exc).__name__)


@router.post("/{document_id}/retry", status_code=202, response_model=DocumentResponseSchema)
async def retry_document(document_id: UUID, assistant_id: UUID,
                         current_user: dict = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    document = await document_service.retry_document(document_id, assistant_id, current_user["id"], db)
    await _dispatch_document(document.id)
    return document
