"""Phase 4 hourly input and simulation results."""
from alembic import op
import sqlalchemy as sa

revision = "003_phase4"
down_revision = "002_phase3"
branch_labels = None
depends_on = None

id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table("load_timeseries", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("enterprise_id", id_type, sa.ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False), sa.Column("timestamp", sa.DateTime(), nullable=False), sa.Column("load_kwh", sa.Float(), nullable=False), sa.Column("irradiation_wm2", sa.Float(), nullable=False, server_default="0"), sa.Column("temperature_c", sa.Float()), sa.Column("humidity_pct", sa.Float()), sa.Column("source", sa.String(300)), sa.CheckConstraint("load_kwh >= 0", name="ck_load_nonnegative"), sa.CheckConstraint("irradiation_wm2 >= 0", name="ck_irradiation_nonnegative"), sa.UniqueConstraint("enterprise_id", "timestamp", name="uq_enterprise_load_ts"))
    op.create_index("ix_load_timeseries_enterprise_id", "load_timeseries", ["enterprise_id"])
    op.create_index("ix_load_timeseries_timestamp", "load_timeseries", ["timestamp"])
    op.create_table("simulation_hour_result", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("task_id", id_type, sa.ForeignKey("simulation_task.id", ondelete="CASCADE"), nullable=False), sa.Column("scenario_id", id_type, sa.ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False), sa.Column("timestamp", sa.DateTime(), nullable=False), sa.Column("load_base_kwh", sa.Float(), server_default="0"), sa.Column("hvac_saved_kwh", sa.Float(), server_default="0"), sa.Column("lighting_saved_kwh", sa.Float(), server_default="0"), sa.Column("load_after_saving_kwh", sa.Float(), server_default="0"), sa.Column("pv_generation_kwh", sa.Float(), server_default="0"), sa.Column("pv_self_use_kwh", sa.Float(), server_default="0"), sa.Column("pv_export_kwh", sa.Float(), server_default="0"), sa.Column("grid_power_kwh", sa.Float(), server_default="0"), sa.Column("carbon_emission_t", sa.Float(), server_default="0"), sa.Column("electricity_cost", sa.Float(), server_default="0"), sa.Column("feed_in_revenue", sa.Float(), server_default="0"), sa.UniqueConstraint("task_id", "timestamp", name="uq_task_hour"))
    op.create_index("ix_simulation_hour_result_task_id", "simulation_hour_result", ["task_id"])
    op.create_index("ix_simulation_hour_result_scenario_id", "simulation_hour_result", ["scenario_id"])
    op.create_index("ix_simulation_hour_result_timestamp", "simulation_hour_result", ["timestamp"])


def downgrade() -> None:
    op.drop_table("simulation_hour_result")
    op.drop_table("load_timeseries")
