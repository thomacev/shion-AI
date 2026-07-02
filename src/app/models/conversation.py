import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SqlEnum
import uuid
from enum import Enum
from datetime import datetime, timezone
from app.db.session import Base


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.assistant import Assistant


class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base):
    __tablename__ = "conversations"

    id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    assistant_id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("assistants.id"), index=True
    )
    title: so.Mapped[str | None] = so.mapped_column(sa.String(256), nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    assistant: so.Mapped["Assistant"] = so.relationship("Assistant", back_populates="conversations") 
    messages: so.Mapped[list["Message"]] = so.relationship(
        "Message", back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("conversations.id"), index=True
    )
    role: so.Mapped[MessageRole] = so.mapped_column(SqlEnum(MessageRole))
    content: so.Mapped[str] = so.mapped_column(sa.Text)
    
    # Guardás los tokens para poder calcular uso después
    tokens_used: so.Mapped[int | None] = so.mapped_column(sa.Integer, nullable=True)
    
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    conversation: so.Mapped["Conversation"] = so.relationship(
        "Conversation", back_populates="messages"
    )