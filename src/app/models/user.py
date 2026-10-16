import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.assistant import Assistant


class User(Base):
    __tablename__ = "users"

    id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: so.Mapped[str] = so.mapped_column(sa.String(128), unique=True, index=True)
    password: so.Mapped[str] = so.mapped_column(sa.String(256), nullable=False)
    full_name: so.Mapped[str] = so.mapped_column(sa.String(64))
    is_active: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=True)
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    # one user can have multiple assistants, one to many relationship
    assistants: so.Mapped[list["Assistant"]] = so.relationship(
        "Assistant", back_populates="user", cascade="all, delete-orphan"
    )
