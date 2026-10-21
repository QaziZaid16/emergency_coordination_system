"""add rotating refresh credentials for remembered sessions

Revision ID: 78f7c901c52a
Revises: de28b59bc889
Create Date: 2026-10-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "78f7c901c52a"
down_revision = "de28b59bc889"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "auth_sessions",
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_auth_sessions_refresh_token_hash",
        "auth_sessions",
        ["refresh_token_hash"],
        unique=True,
        sqlite_where=sa.text("refresh_token_hash IS NOT NULL"),
        postgresql_where=sa.text("refresh_token_hash IS NOT NULL"),
    )


def downgrade():
    op.drop_index(
        "uq_auth_sessions_refresh_token_hash",
        table_name="auth_sessions",
    )
    op.drop_column("auth_sessions", "refresh_token_hash")
