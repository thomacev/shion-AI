"""Persist optional general knowledge mode and answer provenance.

Revision ID: d3e5f708192a
Revises: ef4d56b1d7f0
"""
from alembic import op
import sqlalchemy as sa

revision = "d3e5f708192a"
down_revision = "ef4d56b1d7f0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column(
        "allow_general_knowledge", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))
    # Historical messages have unknown provenance; do not infer it from today's mode.
    op.add_column("messages", sa.Column("answer_basis", sa.String(32), nullable=True))


def downgrade():
    op.drop_column("messages", "answer_basis")
    op.drop_column("conversations", "allow_general_knowledge")
