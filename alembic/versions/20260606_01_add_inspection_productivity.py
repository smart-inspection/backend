from alembic import op
import sqlalchemy as sa


revision = "20260606_01"
down_revision = "20260515_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inspection_productivity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inspectionid", sa.Integer(), nullable=False),
        sa.Column("inspectorname", sa.String(length=150), nullable=True),
        sa.Column("scheduleddate", sa.Date(), nullable=True),
        sa.Column("reportstartedat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reportfinishedat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("durationminutes", sa.Float(), nullable=True),
        sa.Column("operationalstatus", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("metgoal", sa.Boolean(), nullable=True),
        sa.Column("createdat", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updatedat", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["inspectionid"], ["inspections.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inspectionid"),
    )
    op.create_index(
        "ix_inspection_productivity_id",
        "inspection_productivity",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_productivity_inspectionid",
        "inspection_productivity",
        ["inspectionid"],
        unique=True,
    )
    op.create_index(
        "ix_inspection_productivity_inspectorname",
        "inspection_productivity",
        ["inspectorname"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_productivity_scheduleddate",
        "inspection_productivity",
        ["scheduleddate"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_productivity_operationalstatus",
        "inspection_productivity",
        ["operationalstatus"],
        unique=False,
    )
    op.create_index(
        "ix_inspection_productivity_metgoal",
        "inspection_productivity",
        ["metgoal"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_inspection_productivity_metgoal", table_name="inspection_productivity")
    op.drop_index("ix_inspection_productivity_operationalstatus", table_name="inspection_productivity")
    op.drop_index("ix_inspection_productivity_scheduleddate", table_name="inspection_productivity")
    op.drop_index("ix_inspection_productivity_inspectorname", table_name="inspection_productivity")
    op.drop_index("ix_inspection_productivity_inspectionid", table_name="inspection_productivity")
    op.drop_index("ix_inspection_productivity_id", table_name="inspection_productivity")
    op.drop_table("inspection_productivity")