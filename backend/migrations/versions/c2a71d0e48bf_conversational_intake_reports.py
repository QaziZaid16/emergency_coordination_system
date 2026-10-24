"""persist intake answers, assisted updates, and resolution reports

Revision ID: c2a71d0e48bf
Revises: 9ce4b8b2241a
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "c2a71d0e48bf"
down_revision = "9ce4b8b2241a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("incidents") as batch:
        batch.add_column(sa.Column("intake_data", sa.JSON(), nullable=False, server_default="{}"))
    with op.batch_alter_table("incident_updates") as batch:
        batch.add_column(sa.Column("original_message", sa.String(1000), nullable=True))
        batch.add_column(sa.Column("ai_assisted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "incident_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(16), nullable=False, server_default="generated"),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("source_records", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("generated_by", sa.String(32), nullable=False, server_default="evidence_template"),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("incident_id", "version", name="uq_incident_report_version"),
    )
    op.create_index("ix_incident_reports_incident_id", "incident_reports", ["incident_id"])
    op.create_index("ix_incident_reports_status", "incident_reports", ["status"])


def downgrade():
    op.drop_index("ix_incident_reports_status", table_name="incident_reports")
    op.drop_index("ix_incident_reports_incident_id", table_name="incident_reports")
    op.drop_table("incident_reports")
    with op.batch_alter_table("incident_updates") as batch:
        batch.drop_column("ai_assisted")
        batch.drop_column("original_message")
    with op.batch_alter_table("incidents") as batch:
        batch.drop_column("intake_data")
