from alembic import op
import sqlalchemy as sa

revision = "20260606_02"
down_revision = "20260606_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspection_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=150), nullable=False),
        sa.Column("contact_name", sa.String(length=150), nullable=False),
        sa.Column("contact_email", sa.String(length=150), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("requested_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("service_type", sa.String(length=100), nullable=True),
        sa.Column("equipment_type", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_inspection_requests_id",
        "inspection_requests",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_requests_company_name",
        "inspection_requests",
        ["company_name"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_requests_contact_email",
        "inspection_requests",
        ["contact_email"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_requests_requested_date",
        "inspection_requests",
        ["requested_date"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_requests_status",
        "inspection_requests",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_inspection_requests_status", table_name="inspection_requests")
    op.drop_index("ix_inspection_requests_requested_date", table_name="inspection_requests")
    op.drop_index("ix_inspection_requests_contact_email", table_name="inspection_requests")
    op.drop_index("ix_inspection_requests_company_name", table_name="inspection_requests")
    op.drop_index("ix_inspection_requests_id", table_name="inspection_requests")
    op.drop_table("inspection_requests")