"""preserve uploaded public dataset provenance and source columns

Revision ID: f4a2d610c981
Revises: efc190e2d7a4
Create Date: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa


revision = "f4a2d610c981"
down_revision = "efc190e2d7a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("public_dataset_syncs", sa.Column("dataset_name", sa.String(120)))
    op.add_column("public_dataset_syncs", sa.Column("source_filename", sa.String(240)))
    op.add_column("public_dataset_syncs", sa.Column("provenance", sa.String(500)))
    op.add_column("public_dataset_syncs", sa.Column("geographic_scope", sa.String(120)))

    op.add_column("public_earthquakes", sa.Column("source_key", sa.String(32), nullable=False, server_default="usgs_earthquake_catalog"))
    op.create_index("ix_public_earthquakes_source_key", "public_earthquakes", ["source_key"])
    with op.batch_alter_table("public_earthquakes") as batch:
        batch.alter_column("event_url", existing_type=sa.String(1000), nullable=True)
        batch.add_column(sa.Column("title", sa.String(500)))
        batch.add_column(sa.Column("cdi", sa.Float()))
        batch.add_column(sa.Column("mmi", sa.Float()))
        batch.add_column(sa.Column("alert", sa.String(24)))
        batch.add_column(sa.Column("tsunami", sa.Boolean()))
        batch.add_column(sa.Column("significance", sa.Integer()))
        batch.add_column(sa.Column("network", sa.String(32)))
        batch.add_column(sa.Column("station_count", sa.Integer()))
        batch.add_column(sa.Column("minimum_distance", sa.Float()))
        batch.add_column(sa.Column("azimuthal_gap", sa.Float()))
        batch.add_column(sa.Column("magnitude_type", sa.String(32)))
        batch.add_column(sa.Column("location", sa.String(500)))
        batch.add_column(sa.Column("continent", sa.String(120)))
        batch.add_column(sa.Column("country", sa.String(120)))

    op.add_column("public_fema_declarations", sa.Column("source_key", sa.String(32), nullable=False, server_default="fema_disaster_declarations"))
    op.create_index("ix_public_fema_declarations_source_key", "public_fema_declarations", ["source_key"])
    with op.batch_alter_table("public_fema_declarations") as batch:
        batch.alter_column("declaration_type", existing_type=sa.String(8), type_=sa.String(32), existing_nullable=False)
        batch.add_column(sa.Column("close_date", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("individual_assistance", sa.Boolean()))
        batch.add_column(sa.Column("individuals_households_program", sa.Boolean()))
        batch.add_column(sa.Column("public_assistance", sa.Boolean()))
        batch.add_column(sa.Column("hazard_mitigation", sa.Boolean()))


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT 1 FROM public_fema_declarations WHERE length(declaration_type) > 8 LIMIT 1"
    )).first():
        raise RuntimeError(
            "Cannot downgrade while uploaded declaration types exceed the legacy 8-character field. "
            "Export or remove only those uploaded historical rows before retrying."
        )
    with op.batch_alter_table("public_fema_declarations") as batch:
        batch.drop_column("hazard_mitigation")
        batch.drop_column("public_assistance")
        batch.drop_column("individuals_households_program")
        batch.drop_column("individual_assistance")
        batch.drop_column("close_date")
        batch.alter_column("declaration_type", existing_type=sa.String(32), type_=sa.String(8), existing_nullable=False)
    op.drop_index("ix_public_fema_declarations_source_key", table_name="public_fema_declarations")
    op.drop_column("public_fema_declarations", "source_key")

    with op.batch_alter_table("public_earthquakes") as batch:
        batch.drop_column("country")
        batch.drop_column("continent")
        batch.drop_column("location")
        batch.drop_column("magnitude_type")
        batch.drop_column("azimuthal_gap")
        batch.drop_column("minimum_distance")
        batch.drop_column("station_count")
        batch.drop_column("network")
        batch.drop_column("significance")
        batch.drop_column("tsunami")
        batch.drop_column("alert")
        batch.drop_column("mmi")
        batch.drop_column("cdi")
        batch.drop_column("title")
        batch.alter_column("event_url", existing_type=sa.String(1000), nullable=False)
    op.drop_index("ix_public_earthquakes_source_key", table_name="public_earthquakes")
    op.drop_column("public_earthquakes", "source_key")
    op.drop_column("public_dataset_syncs", "geographic_scope")
    op.drop_column("public_dataset_syncs", "provenance")
    op.drop_column("public_dataset_syncs", "source_filename")
    op.drop_column("public_dataset_syncs", "dataset_name")
