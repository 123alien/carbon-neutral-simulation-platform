"""P0-5 hourly storage and curtailment results."""
from alembic import op
import sqlalchemy as sa

revision = "006_p0_5"
down_revision = "005_p0_4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ["storage_charge_kwh", "storage_discharge_kwh", "storage_soc_kwh", "curtailed_pv_kwh", "energy_balance_error_kwh"]:
        op.add_column("simulation_hour_result", sa.Column(name, sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    for name in reversed(["storage_charge_kwh", "storage_discharge_kwh", "storage_soc_kwh", "curtailed_pv_kwh", "energy_balance_error_kwh"]):
        op.drop_column("simulation_hour_result", name)
