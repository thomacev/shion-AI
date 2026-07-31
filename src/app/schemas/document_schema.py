from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.document import DocumentStatus


class DocumentResponseSchema(BaseModel):
    id: UUID
    assistant_id: UUID
    filename: str
    status: DocumentStatus
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)