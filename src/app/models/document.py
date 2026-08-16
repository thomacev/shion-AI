import uuid
from datetime import datetime, timezone
from enum import Enum

import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.core.config import settings
from app.db.session import Base

class DocumentStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    assistant_id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("assistants.id"), index=True
    )
    filename: so.Mapped[str] = so.mapped_column(sa.String(256))
    status: so.Mapped[DocumentStatus] = so.mapped_column(
        sa.Enum(DocumentStatus), default=DocumentStatus.PENDING
    )
    error_message: so.Mapped[str | None] = so.mapped_column(sa.Text, nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    content_type: so.Mapped[str | None] = so.mapped_column(sa.String(128), nullable=True)
    original_content: so.Mapped[bytes | None] = so.mapped_column(sa.LargeBinary, nullable=True)
    chunks: so.Mapped[list["DocumentChunk"]] = so.relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("documents.id"), index=True
    )
    content: so.Mapped[str] = so.mapped_column(sa.Text)
    chunk_index: so.Mapped[int] = so.mapped_column(sa.Integer)
    embedding: so.Mapped[list[float]] = so.mapped_column(Vector(settings.EMBEDDING_DIM))
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    document: so.Mapped["Document"] = so.relationship("Document", back_populates="chunks")