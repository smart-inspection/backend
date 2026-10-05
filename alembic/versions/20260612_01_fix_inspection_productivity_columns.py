from alembic import op
import sqlalchemy as sa

revision = "20260612_01"
down_revision = "20260606_04"
branch_labels = None
depends_on = None

TABLE_NAME = "inspection_productivity"

RENAME_MAP = {
    "inspectionid": "inspection_id",
    "inspectorname": "inspector_name",
    "scheduleddate": "scheduled_date",
    "reportstartedat": "report_started_at",
    "reportfinishedat": "report_finished_at",
    "durationminutes": "duration_minutes",
    "operationalstatus": "operational_status",
    "metgoal": "met_goal",
    "createdat": "created_at",
    "updatedat": "updated_at",
}


def _get_columns(inspector) -> dict[str, dict]:
    return {
        column["name"]: column
        for column in inspector.get_columns(TABLE_NAME)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE_NAME not in inspector.get_table_names():
        return

    columns = _get_columns(inspector)

    with op.batch_alter_table(TABLE_NAME) as batch_op:
        for old_name, new_name in RENAME_MAP.items():
            if old_name in columns and new_name not in columns:
                batch_op.alter_column(
                    old_name,
                    new_column_name=new_name,
                    existing_type=columns[old_name]["type"],
                    existing_nullable=columns[old_name]["nullable"],
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE_NAME not in inspector.get_table_names():
        return

    reverse_map = {new_name: old_name for old_name, new_name in RENAME_MAP.items()}
    columns = _get_columns(inspector)

    with op.batch_alter_table(TABLE_NAME) as batch_op:
        for current_name, old_name in reverse_map.items():
            if current_name in columns and old_name not in columns:
                batch_op.alter_column(
                    current_name,
                    new_column_name=old_name,
                    existing_type=columns[current_name]["type"],
                    existing_nullable=columns[current_name]["nullable"],
                )