from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_validator, Field
from app.models.conversation import MessageRole
from app.core.config import settings


# el usuario puede dar el titulo
# o podria crearlo la IA basandose en las primeras palabras del mensaje, pero eso es mas complicado
class ConversationCreateSchema(BaseModel):
    title: str | None = None
    use_rag: bool = True

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
    use_rag: bool | None = None

    @field_validator("use_rag")
    @classmethod
    def reject_null_rag(cls, value):
        if value is None:
            raise ValueError("use_rag must be true or false")
        return value

class ConversationResponseSchema(BaseModel):
    id: UUID
    assistant_id: UUID
    title: str | None
    use_rag: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# el rol no lo elige el usuario, sino que lo cambia el frontend en todo caso
class MessageCreateSchema(BaseModel):
    content: str = Field(max_length=settings.MAX_MESSAGE_CHARS)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str):
        value = value.strip()

        if not value:
            raise ValueError("Message content cannot be empty.")

        return value


class SourceSchema(BaseModel):
    source_id: str
    document_id: UUID
    filename: str
    chunk_index: int
    page_start: int | None = None
    page_end: int | None = None


class MessageResponseSchema(BaseModel):
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    tokens_used: int | None
    sources: list[SourceSchema] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatResponseSchema(BaseModel):
    message: MessageResponseSchema
    tokens_used: int | None
    model: str | None
