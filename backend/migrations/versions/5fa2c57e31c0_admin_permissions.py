"""store explicit permissions for administrative accounts

Revision ID: 5fa2c57e31c0
Revises: 1bcb3409a6a1
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = "5fa2c57e31c0"
down_revision = "1bcb3409a6a1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("permissions", sa.JSON(), nullable=False, server_default="[]"))
    connection = op.get_bind()
    legacy_root = connection.execute(
        sa.text("SELECT id FROM users WHERE role = 'admin' AND active IS TRUE ORDER BY created_at, id LIMIT 1")
    ).first()
    if legacy_root:
        connection.execute(
            sa.text("UPDATE users SET role = 'super_admin' WHERE id = :user_id"),
            {"user_id": legacy_root[0]},
        )


def downgrade():
    op.drop_column("users", "permissions")
