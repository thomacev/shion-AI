from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.conversation import MessageRole

#el rol no lo elige el usuario, sino que lo cambia el frontend en todo caso
class MessageCreateSchema(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Message content cannot be empty.")

        return value


class MessageResponseSchema(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    tokens_used: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)