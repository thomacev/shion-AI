from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

#el usuario puede dar el titulo
#o podria crearlo la IA basandose en las primeras palabras del mensaje, pero eso es mas complicado
class ConversationCreateSchema(BaseModel):
    title: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None):
        if value is None:
            return value

        value = value.strip()

        if len(value) > 256:
            raise ValueError("Conversation title cannot exceed 256 characters.")

        return value


class ConversationUpdateSchema(BaseModel):
    title: str

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Conversation title cannot be empty.")

        if len(value) > 256:
            raise ValueError("Conversation title cannot exceed 256 characters.")

        return value


class ConversationResponseSchema(BaseModel):
    id: UUID
    assistant_id: UUID
    title: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)