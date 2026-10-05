from alembic import op
import sqlalchemy as sa

revision = "20260606_03"
down_revision = "20260606_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inspectionrequests",
        sa.Column("inspection_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_inspectionrequests_inspection_id",
        "inspectionrequests",
        ["inspection_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_inspectionrequests_inspection_id_inspections",
        "inspectionrequests",
        "inspections",
        ["inspection_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_inspectionrequests_inspection_id_inspections",
        "inspectionrequests",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_inspectionrequests_inspection_id",
        table_name="inspectionrequests",
    )
    op.drop_column("inspectionrequests", "inspection_id")