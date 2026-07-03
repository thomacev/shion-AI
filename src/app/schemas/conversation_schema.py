from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.conversation import MessageRole

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


class ConversationResponseSchema(BaseModel):
    id: UUID
    assistant_id: UUID
    title: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

class ChatResponseSchema(BaseModel):
    message: MessageResponseSchema
    tokens_used: int | None
    model: str | None
