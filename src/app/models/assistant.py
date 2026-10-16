import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


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
        sa.Text, default="You are a helpful assistant."
    )

    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: so.Mapped["User"] = so.relationship("User", back_populates="assistants")
    conversations: so.Mapped[list["Conversation"]] = so.relationship(
        "Conversation", back_populates="assistant", cascade="all, delete-orphan"
    )
