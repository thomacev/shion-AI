import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from app.db.session import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.conversation import Conversation

class Assistant(Base):
    __tablename__ = "assistants"

    id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("users.id"), index=True
    )
    name: so.Mapped[str] = so.mapped_column(sa.String(128))
    description: so.Mapped[str | None] = so.mapped_column(sa.String(512), nullable=True)
    
    # The system prompt is a message that defines the behavior of the assistant.
    system_prompt: so.Mapped[str] = so.mapped_column(
        sa.Text,
        default="You are a helpful assistant."
    )
    
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user: so.Mapped["User"] = so.relationship("User", back_populates="assistants") 
    conversations: so.Mapped[list["Conversation"]] = so.relationship("Conversation", back_populates="assistant", cascade="all, delete-orphan") 