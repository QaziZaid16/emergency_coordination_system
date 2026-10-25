"""add ownership token for each incident analysis attempt

Revision ID: 4e5b0b6a92d1
Revises: c2a71d0e48bf
Create Date: 2026-10-25
"""
from alembic import op
import sqlalchemy as sa


revision = "4e5b0b6a92d1"
down_revision = "c2a71d0e48bf"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("incident_analyses") as batch:
        batch.add_column(sa.Column("claim_token", sa.String(length=36), nullable=True))


def downgrade():
    with op.batch_alter_table("incident_analyses") as batch:
        batch.drop_column("claim_token")
