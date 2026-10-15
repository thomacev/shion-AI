"""Document claims, embedding provenance, source citations and generation claims.

Revision ID: c2d4e6f81012
Revises: baff9cff71dd
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "c2d4e6f81012"
down_revision = "baff9cff71dd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("processing_token", UUID(as_uuid=True), nullable=True))
    op.add_column("documents", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    # Legacy vectors have unknown provenance until explicitly reprocessed.
    op.add_column("documents", sa.Column("embedding_model", sa.String(128), nullable=True))
    op.add_column("documents", sa.Column("embedding_dim", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("page_start", sa.Integer(), nullable=True))
    op.add_column("document_chunks", sa.Column("page_end", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_document_chunk_index", "document_chunks", ["document_id", "chunk_index"])
    op.create_index("ix_document_chunks_embedding_hnsw", "document_chunks", ["embedding"],
                    postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"})
    op.add_column("conversations", sa.Column("generation_token", UUID(as_uuid=True), nullable=True))
    op.add_column("conversations", sa.Column("generation_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("messages", sa.Column("sources", JSONB(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("messages", "sources")
    op.drop_column("conversations", "generation_expires_at")
    op.drop_column("conversations", "generation_token")
    op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
    op.drop_constraint("uq_document_chunk_index", "document_chunks", type_="unique")
    op.drop_column("document_chunks", "page_end")
    op.drop_column("document_chunks", "page_start")
    for name in ("embedding_dim", "embedding_model", "attempts", "next_attempt_at",
                 "lease_expires_at", "processing_token"):
        op.drop_column("documents", name)
