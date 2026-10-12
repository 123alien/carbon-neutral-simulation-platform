"""P1-3 wind generation and EV charging hourly results."""
from alembic import op
import sqlalchemy as sa
revision="010_p1_3";down_revision="009_p1_2";branch_labels=None;depends_on=None
FIELDS=["ev_charging_load_kwh","wind_generation_kwh","wind_self_use_kwh","wind_export_kwh","renewable_generation_kwh","renewable_export_kwh","curtailed_renewable_kwh"]
def upgrade():
    for name in FIELDS:op.add_column("simulation_hour_result",sa.Column(name,sa.Float(),nullable=False,server_default="0"))
def downgrade():
    for name in reversed(FIELDS):op.drop_column("simulation_hour_result",name)
