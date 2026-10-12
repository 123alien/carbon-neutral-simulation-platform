"""Phase 1-2 initial annual simulation schema."""
from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table("enterprise", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("name", sa.String(200), nullable=False), sa.Column("region", sa.String(100)), sa.Column("industry", sa.String(100)), sa.Column("building_area", sa.Float()), sa.Column("population", sa.Integer()), sa.Column("latitude", sa.Float()), sa.Column("longitude", sa.Float()), sa.Column("base_year", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_table("emission_factor", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("region", sa.String(100), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("energy_type", sa.String(50), nullable=False), sa.Column("factor", sa.Float(), nullable=False), sa.Column("unit", sa.String(50), nullable=False), sa.Column("source", sa.String(500)), sa.Column("version", sa.String(80), nullable=False), sa.UniqueConstraint("region", "year", "energy_type", "version", name="uq_emission_factor"))
    op.create_index("ix_emission_factor_region", "emission_factor", ["region"])
    op.create_index("ix_emission_factor_year", "emission_factor", ["year"])
    op.create_index("ix_emission_factor_energy_type", "emission_factor", ["energy_type"])
    op.create_table("energy_history", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("enterprise_id", id_type, sa.ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("month", sa.Integer()), sa.Column("energy_type", sa.String(50), nullable=False), sa.Column("consumption", sa.Float(), nullable=False), sa.Column("unit", sa.String(30), nullable=False), sa.Column("source", sa.String(300)), sa.UniqueConstraint("enterprise_id", "year", "month", "energy_type", name="uq_energy_history"))
    op.create_index("ix_energy_history_enterprise_id", "energy_history", ["enterprise_id"])
    op.create_table("scenario", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("enterprise_id", id_type, sa.ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("description", sa.Text()), sa.Column("base_year", sa.Integer(), nullable=False), sa.Column("start_year", sa.Integer(), nullable=False), sa.Column("end_year", sa.Integer(), nullable=False), sa.Column("target_peak_year", sa.Integer()), sa.Column("target_neutral_year", sa.Integer()), sa.Column("baseline_growth_json", sa.JSON(), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime()))
    op.create_index("ix_scenario_enterprise_id", "scenario", ["enterprise_id"])
    op.create_table("scenario_measure", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("scenario_id", id_type, sa.ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False), sa.Column("measure_type", sa.String(50), nullable=False), sa.Column("start_year", sa.Integer(), nullable=False), sa.Column("end_year", sa.Integer()), sa.Column("parameters_json", sa.JSON(), nullable=False))
    op.create_index("ix_scenario_measure_scenario_id", "scenario_measure", ["scenario_id"])
    op.create_table("simulation_task", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("scenario_id", id_type, sa.ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("parameter_snapshot_json", sa.JSON(), nullable=False), sa.Column("summary_json", sa.JSON()), sa.Column("started_at", sa.DateTime()), sa.Column("finished_at", sa.DateTime()), sa.Column("error_message", sa.Text()))
    op.create_index("ix_simulation_task_scenario_id", "simulation_task", ["scenario_id"])
    op.create_table("simulation_year_result", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("task_id", id_type, sa.ForeignKey("simulation_task.id", ondelete="CASCADE"), nullable=False), sa.Column("scenario_id", id_type, sa.ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False), sa.Column("year", sa.Integer(), nullable=False), sa.Column("electricity_base_kwh", sa.Float(), server_default="0"), sa.Column("electricity_after_saving_kwh", sa.Float(), server_default="0"), sa.Column("grid_power_kwh", sa.Float(), server_default="0"), sa.Column("natural_gas_kwh", sa.Float(), server_default="0"), sa.Column("pv_generation_kwh", sa.Float(), server_default="0"), sa.Column("pv_self_use_kwh", sa.Float(), server_default="0"), sa.Column("pv_export_kwh", sa.Float(), server_default="0"), sa.Column("energy_saved_kwh", sa.Float(), server_default="0"), sa.Column("carbon_emission_t", sa.Float(), server_default="0"), sa.Column("carbon_reduction_t", sa.Float(), server_default="0"), sa.Column("investment", sa.Float(), server_default="0"), sa.Column("annual_benefit", sa.Float(), server_default="0"), sa.UniqueConstraint("task_id", "year", name="uq_task_year"))
    op.create_index("ix_simulation_year_result_task_id", "simulation_year_result", ["task_id"])
    op.create_index("ix_simulation_year_result_scenario_id", "simulation_year_result", ["scenario_id"])


def downgrade() -> None:
    for table in ["simulation_year_result", "simulation_task", "scenario_measure", "scenario", "energy_history", "emission_factor", "enterprise"]:
        op.drop_table(table)
