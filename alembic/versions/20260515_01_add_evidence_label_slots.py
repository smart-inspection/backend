"""add evidence label slots

Revision ID: 20260515_01
Revises: <TU_REVISION_ANTERIOR>
Create Date: 2026-05-15 11:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260515_01"
down_revision = "<TU_REVISION_ANTERIOR>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evidences", sa.Column("raw_label", sa.String(length=120), nullable=True))
    op.add_column("evidences", sa.Column("normalized_label", sa.String(length=120), nullable=True))
    op.add_column("evidences", sa.Column("evidence_slot", sa.String(length=120), nullable=True))
    op.add_column("evidences", sa.Column("component_code", sa.String(length=80), nullable=True))
    op.add_column("evidences", sa.Column("axle_number", sa.Integer(), nullable=True))
    op.add_column("evidences", sa.Column("side", sa.String(length=20), nullable=True))
    op.add_column("evidences", sa.Column("is_reference", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.add_column("evidences", sa.Column("label_confidence", sa.Numeric(5, 2), nullable=True))
    op.add_column("evidences", sa.Column("metadata_json", sa.JSON(), nullable=True))

    op.create_index("ix_evidences_raw_label", "evidences", ["raw_label"])
    op.create_index("ix_evidences_normalized_label", "evidences", ["normalized_label"])
    op.create_index("ix_evidences_evidence_slot", "evidences", ["evidence_slot"])
    op.create_index("ix_evidences_component_code", "evidences", ["component_code"])
    op.create_index("ix_evidences_axle_number", "evidences", ["axle_number"])
    op.create_index("ix_evidences_side", "evidences", ["side"])


def downgrade() -> None:
    op.drop_index("ix_evidences_side", table_name="evidences")
    op.drop_index("ix_evidences_axle_number", table_name="evidences")
    op.drop_index("ix_evidences_component_code", table_name="evidences")
    op.drop_index("ix_evidences_evidence_slot", table_name="evidences")
    op.drop_index("ix_evidences_normalized_label", table_name="evidences")
    op.drop_index("ix_evidences_raw_label", table_name="evidences")

    op.drop_column("evidences", "metadata_json")
    op.drop_column("evidences", "label_confidence")
    op.drop_column("evidences", "is_reference")
    op.drop_column("evidences", "side")
    op.drop_column("evidences", "axle_number")
    op.drop_column("evidences", "component_code")
    op.drop_column("evidences", "evidence_slot")
    op.drop_column("evidences", "normalized_label")
    op.drop_column("evidences", "raw_label")