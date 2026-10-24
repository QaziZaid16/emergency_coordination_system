"""track persisted analysis job attempts for restart recovery

Revision ID: 9ce4b8b2241a
Revises: b271c7e05d3a
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa


revision = "9ce4b8b2241a"
down_revision = "b271c7e05d3a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("incident_analyses") as batch:
        batch.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("last_error_type", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("incident_analyses") as batch:
        batch.drop_column("last_attempt_at")
        batch.drop_column("last_error_type")
        batch.drop_column("attempt_count")
