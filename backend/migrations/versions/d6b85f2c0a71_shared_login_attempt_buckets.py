"""add shared login attempt buckets

Revision ID: d6b85f2c0a71
Revises: 4e5b0b6a92d1
Create Date: 2026-10-25
"""

from alembic import op
import sqlalchemy as sa


revision = "d6b85f2c0a71"
down_revision = "4e5b0b6a92d1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_attempt_buckets",
        sa.Column("identifier_hash", sa.String(length=64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_login_attempt_buckets_window",
        "login_attempt_buckets",
        ["window_started_at"],
    )


def downgrade():
    op.drop_index(
        "ix_login_attempt_buckets_window", table_name="login_attempt_buckets"
    )
    op.drop_table("login_attempt_buckets")
