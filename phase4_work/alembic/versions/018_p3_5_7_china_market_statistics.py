"""P3-5.7 official China market statistic fields."""
from alembic import op
import sqlalchemy as sa

revision="018_p3_5_7";down_revision="017_p3_5_2_1";branch_labels=None;depends_on=None

def upgrade():
    with op.batch_alter_table("carbon_market_timeseries") as b:
        b.add_column(sa.Column("trading_amount_yuan",sa.Float()))
        b.add_column(sa.Column("ccer_trading_amount_yuan",sa.Float()))
        b.add_column(sa.Column("green_certificate_issued_count",sa.Float()))
        b.add_column(sa.Column("green_certificate_traded_count",sa.Float()))

def downgrade():
    with op.batch_alter_table("carbon_market_timeseries") as b:
        for name in ("green_certificate_traded_count","green_certificate_issued_count","ccer_trading_amount_yuan","trading_amount_yuan"):
            b.drop_column(name)
