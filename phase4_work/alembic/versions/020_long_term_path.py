"""Long-term annual carbon path projection snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "020_long_term_path"
down_revision = "019_park_centered_data_sources"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "long_term_path_run",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("enterprise_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_version_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey("scenario_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("baseline_task_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), sa.ForeignKey("simulation_task.id", ondelete="RESTRICT")),
        sa.Column("status", sa.String(30), nullable=False, server_default="SUCCESS"),
        sa.Column("input_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("result_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_long_term_path_run_enterprise_id", "long_term_path_run", ["enterprise_id"])
    op.create_index("ix_long_term_path_run_scenario_version_id", "long_term_path_run", ["scenario_version_id"])
    op.create_index("ix_long_term_path_run_baseline_task_id", "long_term_path_run", ["baseline_task_id"])

def downgrade():
    op.drop_index("ix_long_term_path_run_baseline_task_id", table_name="long_term_path_run")
    op.drop_index("ix_long_term_path_run_scenario_version_id", table_name="long_term_path_run")
    op.drop_index("ix_long_term_path_run_enterprise_id", table_name="long_term_path_run")
    op.drop_table("long_term_path_run")
