"""adding document table

Revision ID: 3371a442b4ca
Revises: 41d3ed46785d
Create Date: 2026-07-27 09:54:37.098105

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '3371a442b4ca'
down_revision: Union[str, Sequence[str], None] = '41d3ed46785d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("assistant_id", UUID(as_uuid=True), sa.ForeignKey("assistants.id"), nullable=False),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "PROCESSING", "READY", "FAILED", name="documentstatus"), nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_documents_assistant_id", "documents", ["assistant_id"])

    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])

    # HNSW en vez de IVFFlat: IVFFlat necesita una cantidad decente de filas
    # para armar buenos clusters, algo que un proyecto de portfolio con pocos
    # documentos nunca va a tener. HNSW funciona bien incluso con pocas filas.
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade():
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.execute("DROP EXTENSION IF EXISTS vector")
