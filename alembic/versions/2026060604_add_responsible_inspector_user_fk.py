from alembic import op
import sqlalchemy as sa


revision = "20260606_04"
down_revision = "20260606_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inspections",
        sa.Column("responsible_inspector_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_inspections_responsible_inspector_id",
        "inspections",
        ["responsible_inspector_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_inspections_responsible_inspector_id_users",
        "inspections",
        "users",
        ["responsible_inspector_id"],
        ["id"],
    )
    op.drop_column("inspections", "responsibleinspector")


def downgrade() -> None:
    op.add_column(
        "inspections",
        sa.Column("responsibleinspector", sa.String(length=150), nullable=True),
    )
    op.drop_constraint(
        "fk_inspections_responsible_inspector_id_users",
        "inspections",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_inspections_responsible_inspector_id",
        table_name="inspections",
    )
    op.drop_column("inspections", "responsible_inspector_id")