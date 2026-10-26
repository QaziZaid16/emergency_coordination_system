"""store bounded USGS and FEMA public historical records separately

Revision ID: efc190e2d7a4
Revises: d6b85f2c0a71
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa


revision = "efc190e2d7a4"
down_revision = "d6b85f2c0a71"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "public_dataset_syncs",
        sa.Column("source", sa.String(32), primary_key=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("range_start", sa.DateTime(timezone=True)),
        sa.Column("range_end", sa.DateTime(timezone=True)),
        sa.Column("imported_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("was_limited", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_error", sa.String(240)),
    )
    op.create_table(
        "public_earthquakes",
        sa.Column("source_id", sa.String(64), primary_key=True),
        sa.Column("magnitude", sa.Float(), nullable=False),
        sa.Column("place", sa.String(500)),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("depth_km", sa.Float()),
        sa.Column("event_url", sa.String(1000), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("attribution", sa.String(240), nullable=False, server_default="USGS Earthquake Hazards Program"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_public_earthquake_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_public_earthquake_longitude"),
    )
    op.create_index("ix_public_earthquakes_event_time", "public_earthquakes", ["event_time"])
    op.create_table(
        "public_fema_declarations",
        sa.Column("source_id", sa.String(64), primary_key=True),
        sa.Column("disaster_number", sa.Integer(), nullable=False),
        sa.Column("declaration_string", sa.String(32)),
        sa.Column("declaration_type", sa.String(8), nullable=False),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column("designated_area", sa.String(240)),
        sa.Column("incident_type", sa.String(120)),
        sa.Column("title", sa.String(500)),
        sa.Column("incident_begin_date", sa.DateTime(timezone=True)),
        sa.Column("incident_end_date", sa.DateTime(timezone=True)),
        sa.Column("declaration_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("attribution", sa.String(240), nullable=False, server_default="FEMA OpenFEMA; not endorsed by FEMA"),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("disaster_number", "declaration_string", "declaration_type", "state", "incident_type", "declaration_date"):
        op.create_index(f"ix_public_fema_declarations_{column}", "public_fema_declarations", [column])


def downgrade():
    op.drop_table("public_fema_declarations")
    op.drop_index("ix_public_earthquakes_event_time", table_name="public_earthquakes")
    op.drop_table("public_earthquakes")
    op.drop_table("public_dataset_syncs")
