"""users, conversations, chat messages; link jobs to users

Revision ID: 0002_users_and_chat
Revises: 0001_initial
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_users_and_chat"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("tenant_id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # Batch mode so the ALTER works on SQLite (CI) as well as Postgres.
    with op.batch_alter_table("research_jobs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("user_id", sa.String(length=32), nullable=True)
        )
        batch_op.create_index("ix_research_jobs_user_id", ["user_id"])
        batch_op.create_foreign_key(
            "fk_research_jobs_user_id",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["research_jobs.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_job_id", "conversations", ["job_id"])
    op.create_index(
        "ix_conversations_created_at", "conversations", ["created_at"]
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_chat_messages_conversation_id",
        "chat_messages",
        ["conversation_id"],
    )
    op.create_index(
        "ix_chat_messages_created_at", "chat_messages", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index(
        "ix_chat_messages_conversation_id", table_name="chat_messages"
    )
    op.drop_table("chat_messages")

    op.drop_index("ix_conversations_created_at", table_name="conversations")
    op.drop_index("ix_conversations_job_id", table_name="conversations")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")

    with op.batch_alter_table("research_jobs", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_research_jobs_user_id", type_="foreignkey"
        )
        batch_op.drop_index("ix_research_jobs_user_id")
        batch_op.drop_column("user_id")

    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")
