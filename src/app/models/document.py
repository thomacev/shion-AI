import uuid
from datetime import UTC, datetime
from enum import Enum

import sqlalchemy as sa
import sqlalchemy.orm as so
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

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
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    content_type: so.Mapped[str | None] = so.mapped_column(sa.String(128), nullable=True)
    original_content: so.Mapped[bytes | None] = so.mapped_column(sa.LargeBinary, nullable=True)
    processing_token: so.Mapped[uuid.UUID | None] = so.mapped_column(UUID(as_uuid=True), nullable=True)
    lease_expires_at: so.Mapped[datetime | None] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)
    next_attempt_at: so.Mapped[datetime | None] = so.mapped_column(sa.DateTime(timezone=True), nullable=True)
    attempts: so.Mapped[int] = so.mapped_column(sa.Integer, default=0, server_default="0")
    embedding_model: so.Mapped[str | None] = so.mapped_column(sa.String(128), nullable=True)
    embedding_dim: so.Mapped[int | None] = so.mapped_column(sa.Integer, nullable=True)
    chunks: so.Mapped[list["DocumentChunk"]] = so.relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        sa.Index("ix_document_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw",
                 postgresql_ops={"embedding": "vector_cosine_ops"}),
    )

    id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: so.Mapped[uuid.UUID] = so.mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("documents.id"), index=True
    )
    content: so.Mapped[str] = so.mapped_column(sa.Text)
    chunk_index: so.Mapped[int] = so.mapped_column(sa.Integer)
    page_start: so.Mapped[int | None] = so.mapped_column(sa.Integer, nullable=True)
    page_end: so.Mapped[int | None] = so.mapped_column(sa.Integer, nullable=True)
    embedding: so.Mapped[list[float]] = so.mapped_column(Vector(settings.EMBEDDING_DIM))
    created_at: so.Mapped[datetime] = so.mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    document: so.Mapped["Document"] = so.relationship("Document", back_populates="chunks")
