"""Phase 3 canonical physical fuel units."""
from alembic import op
import sqlalchemy as sa

revision = "002_phase3"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("simulation_year_result") as batch:
        batch.alter_column("natural_gas_kwh", new_column_name="natural_gas_m3")
        batch.add_column(sa.Column("coal_kg", sa.Float(), server_default="0"))
        batch.add_column(sa.Column("oil_kg", sa.Float(), server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("simulation_year_result") as batch:
        batch.drop_column("oil_kg")
        batch.drop_column("coal_kg")
        batch.alter_column("natural_gas_m3", new_column_name="natural_gas_kwh")
