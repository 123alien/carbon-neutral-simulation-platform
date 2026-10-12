"""P0-4 weather sites and UTC observations."""
from alembic import op
import sqlalchemy as sa

revision = "005_p0_4"
down_revision = "004_p0_2"
branch_labels = None
depends_on = None
id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table("weather_site", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("enterprise_id", id_type, sa.ForeignKey("enterprise.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(200), nullable=False), sa.Column("latitude", sa.Float()), sa.Column("longitude", sa.Float()), sa.Column("timezone", sa.String(100), nullable=False, server_default="UTC"), sa.Column("source", sa.String(300)), sa.Column("created_at", sa.DateTime()))
    op.create_index("ix_weather_site_enterprise_id", "weather_site", ["enterprise_id"])
    op.create_table("weather_timeseries", sa.Column("id", id_type, primary_key=True, autoincrement=True), sa.Column("site_id", id_type, sa.ForeignKey("weather_site.id", ondelete="CASCADE"), nullable=False), sa.Column("timestamp", sa.DateTime(), nullable=False), sa.Column("temperature_c", sa.Float(), nullable=False), sa.Column("humidity_pct", sa.Float(), nullable=False), sa.Column("ghi_w_m2", sa.Float(), nullable=False), sa.Column("dni_w_m2", sa.Float()), sa.Column("dhi_w_m2", sa.Float()), sa.Column("wind_speed_m_s", sa.Float()), sa.Column("cloud_cover_pct", sa.Float()), sa.Column("source", sa.String(300)), sa.CheckConstraint("humidity_pct >= 0 AND humidity_pct <= 100", name="ck_weather_humidity"), sa.CheckConstraint("ghi_w_m2 >= 0", name="ck_weather_ghi"), sa.UniqueConstraint("site_id", "timestamp", name="uq_weather_site_ts"))
    op.create_index("ix_weather_timeseries_site_id", "weather_timeseries", ["site_id"])
    op.create_index("ix_weather_timeseries_timestamp", "weather_timeseries", ["timestamp"])


def downgrade() -> None:
    op.drop_table("weather_timeseries")
    op.drop_table("weather_site")
