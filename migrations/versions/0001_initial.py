"""initial schema: tenants, api_keys, research_jobs, reports

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("tenant_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_prefix", "api_keys", ["prefix"])

    op.create_table(
        "research_jobs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("tenant_id", sa.String(length=32), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("num_sources", sa.Integer(), nullable=False),
        sa.Column("trace", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_research_jobs_tenant_id", "research_jobs", ["tenant_id"])
    op.create_index("ix_research_jobs_status", "research_jobs", ["status"])
    op.create_index("ix_research_jobs_created_at", "research_jobs", ["created_at"])

    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("job_id", sa.String(length=32), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["research_jobs.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("job_id"),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_index("ix_research_jobs_created_at", table_name="research_jobs")
    op.drop_index("ix_research_jobs_status", table_name="research_jobs")
    op.drop_index("ix_research_jobs_tenant_id", table_name="research_jobs")
    op.drop_table("research_jobs")
    op.drop_index("ix_api_keys_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_tenant_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_table("tenants")
