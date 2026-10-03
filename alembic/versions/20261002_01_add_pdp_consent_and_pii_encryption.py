"""add_pdp_consent_and_pii_encryption

Revision ID: 20261002_01
Revises: 20260612_01
Create Date: 2026-10-02 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "20261002_01"
down_revision = "20260612_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Agregar columnas de trazabilidad probatoria de consentimiento (Ley N° 29733)
    op.add_column(
        "inspection_requests",
        sa.Column("consent_accepted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "inspection_requests",
        sa.Column("consent_third_party", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "inspection_requests",
        sa.Column("consent_timestamp", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inspection_requests",
        sa.Column("consent_ip_address", sa.String(length=45), nullable=True),
    )

    # 2. Ampliar columnas para almacenar PII cifrada (AES-256 Fernet)
    op.alter_column(
        "inspection_requests",
        "contact_phone",
        existing_type=sa.String(length=50),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "inspection_requests",
        "contact_email",
        existing_type=sa.String(length=150),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "inspection_requests",
        "contact_email",
        existing_type=sa.String(length=255),
        type_=sa.String(length=150),
        existing_nullable=True,
    )
    op.alter_column(
        "inspection_requests",
        "contact_phone",
        existing_type=sa.String(length=255),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    op.drop_column("inspection_requests", "consent_ip_address")
    op.drop_column("inspection_requests", "consent_timestamp")
    op.drop_column("inspection_requests", "consent_third_party")
    op.drop_column("inspection_requests", "consent_accepted")
