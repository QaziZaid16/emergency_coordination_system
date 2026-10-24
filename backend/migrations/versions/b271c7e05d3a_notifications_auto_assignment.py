"""add persistent in-app notifications and assignment policy

Revision ID: b271c7e05d3a
Revises: a40b1331ee91
Create Date: 2026-10-24
"""
from alembic import op
import sqlalchemy as sa

revision = "b271c7e05d3a"
down_revision = "a40b1331ee91"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("assignments") as batch:
        batch.alter_column("assigned_by", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("assignment_source", sa.String(16), nullable=False, server_default="manual"))
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_key", sa.String(160), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("message", sa.String(240), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "event_key", name="uq_notification_user_event"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_incident_id", "notifications", ["incident_id"])
    op.create_index("ix_notifications_kind", "notifications", ["kind"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_table(
        "coordination_policy",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("auto_assignment_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_assign_max_severity", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(sa.text("INSERT INTO coordination_policy (id, auto_assignment_enabled, auto_assign_max_severity, updated_at) VALUES ('default', false, 3, CURRENT_TIMESTAMP)"))


def downgrade():
    op.drop_table("coordination_policy")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_kind", table_name="notifications")
    op.drop_index("ix_notifications_incident_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("assignment_source")
        batch.alter_column("assigned_by", existing_type=sa.String(36), nullable=False)
