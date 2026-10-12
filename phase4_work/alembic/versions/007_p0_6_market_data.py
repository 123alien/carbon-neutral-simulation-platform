"""P0-6 dynamic prices, grid factors and green power."""
from alembic import op
import sqlalchemy as sa

revision = "007_p0_6"
down_revision = "006_p0_5"
branch_labels = None
depends_on = None
id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table("electricity_price_timeseries", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("enterprise_id", id_type, sa.ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False), sa.Column("timestamp", sa.DateTime(), nullable=False), sa.Column("purchase_price_per_kwh", sa.Float(), nullable=False), sa.Column("feed_in_tariff_per_kwh", sa.Float(), nullable=False, server_default="0"), sa.Column("source", sa.String(300)), sa.UniqueConstraint("enterprise_id", "timestamp", name="uq_enterprise_price_ts"))
    op.create_index("ix_price_enterprise", "electricity_price_timeseries", ["enterprise_id"]); op.create_index("ix_price_timestamp", "electricity_price_timeseries", ["timestamp"])
    op.create_table("grid_emission_factor_timeseries", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("region", sa.String(100), nullable=False), sa.Column("timestamp", sa.DateTime(), nullable=False), sa.Column("factor_kg_per_kwh", sa.Float(), nullable=False), sa.Column("source", sa.String(300)), sa.Column("version", sa.String(80), nullable=False), sa.UniqueConstraint("region", "timestamp", "version", name="uq_grid_factor_ts"))
    op.create_index("ix_grid_factor_region", "grid_emission_factor_timeseries", ["region"]); op.create_index("ix_grid_factor_timestamp", "grid_emission_factor_timeseries", ["timestamp"])
    op.create_table("green_power_contract", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("enterprise_id", id_type, sa.ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("start_at", sa.DateTime(), nullable=False), sa.Column("end_at", sa.DateTime(), nullable=False), sa.Column("purchase_kwh", sa.Float()), sa.Column("purchase_share", sa.Float()), sa.Column("emission_factor_kg_per_kwh", sa.Float(), nullable=False, server_default="0"), sa.Column("premium_per_kwh", sa.Float(), nullable=False, server_default="0"), sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"), sa.Column("source", sa.String(300)))
    op.create_index("ix_green_contract_enterprise", "green_power_contract", ["enterprise_id"])
    for name in ["purchase_price_per_kwh", "feed_in_tariff_per_kwh", "grid_emission_factor_kg_per_kwh", "green_power_kwh", "green_power_emission_t", "green_power_carbon_reduction_t"]:
        op.add_column("simulation_hour_result", sa.Column(name, sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    for name in reversed(["purchase_price_per_kwh", "feed_in_tariff_per_kwh", "grid_emission_factor_kg_per_kwh", "green_power_kwh", "green_power_emission_t", "green_power_carbon_reduction_t"]): op.drop_column("simulation_hour_result", name)
    op.drop_table("green_power_contract"); op.drop_table("grid_emission_factor_timeseries"); op.drop_table("electricity_price_timeseries")
