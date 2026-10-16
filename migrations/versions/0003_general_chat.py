"""general chat: nullable conversation.job_id + conversation.updated_at

Revision ID: 0003_general_chat
Revises: 0002_users_and_chat
Create Date: 2026-10-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_general_chat"
down_revision: Union[str, None] = "0002_users_and_chat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill updated_at from created_at for existing rows.
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.alter_column(
            "job_id", existing_type=sa.String(length=32), nullable=True
        )
    op.execute(
        "UPDATE conversations SET updated_at = created_at WHERE updated_at IS NULL"
    )
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
    op.create_index(
        "ix_conversations_updated_at", "conversations", ["updated_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_updated_at", table_name="conversations")
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.alter_column(
            "job_id", existing_type=sa.String(length=32), nullable=False
        )
        batch_op.drop_column("updated_at")
