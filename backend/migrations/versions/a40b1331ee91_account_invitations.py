"""add expiring one-time responder invitations

Revision ID: a40b1331ee91
Revises: 5fa2c57e31c0
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = "a40b1331ee91"
down_revision = "5fa2c57e31c0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_account_invitations_user_id", "account_invitations", ["user_id"])
    op.create_index("ix_account_invitations_expires_at", "account_invitations", ["expires_at"])


def downgrade():
    op.drop_table("account_invitations")
