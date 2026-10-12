"""P0-2 store normalized power in kW."""
from alembic import op
import sqlalchemy as sa

revision = "004_p0_2"
down_revision = "003_phase4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("load_timeseries", sa.Column("load_kw", sa.Float(), nullable=True))
    op.execute("UPDATE load_timeseries SET load_kw = load_kwh WHERE load_kw IS NULL")


def downgrade() -> None:
    op.drop_column("load_timeseries", "load_kw")
