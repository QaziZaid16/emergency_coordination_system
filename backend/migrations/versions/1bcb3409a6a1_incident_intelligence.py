"""persist validated incident decision support

Revision ID: 1bcb3409a6a1
Revises: 78f7c901c52a
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa


revision = "1bcb3409a6a1"
down_revision = "78f7c901c52a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "incident_analyses",
        sa.Column("incident_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("validation_outcome", sa.String(length=32), nullable=False),
        sa.Column("usage_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("incident_id"),
    )
    op.create_index(
        op.f("ix_incident_analyses_status"),
        "incident_analyses",
        ["status"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_incident_analyses_status"), table_name="incident_analyses")
    op.drop_table("incident_analyses")
