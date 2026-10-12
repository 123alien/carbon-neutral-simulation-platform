"""P3-5.2.1 REST incremental acquisition runtime and external idempotency."""
from alembic import op
import sqlalchemy as sa

revision="017_p3_5_2_1";down_revision="016_p3_4";branch_labels=None;depends_on=None
I=sa.BigInteger().with_variant(sa.Integer(),"sqlite")

def upgrade():
    with op.batch_alter_table("data_source_runtime_state") as b:
        b.add_column(sa.Column("last_success_watermark",sa.DateTime()))
        b.add_column(sa.Column("current_window_start",sa.DateTime()))
        b.add_column(sa.Column("current_window_end",sa.DateTime()))
        b.add_column(sa.Column("requested_pages",sa.Integer(),nullable=False,server_default="0"))
        b.add_column(sa.Column("successful_pages",sa.Integer(),nullable=False,server_default="0"))
        b.add_column(sa.Column("failed_page",sa.Integer()))
        b.add_column(sa.Column("pages_fetched",sa.Integer(),nullable=False,server_default="0"))
        b.add_column(sa.Column("records_fetched",sa.Integer(),nullable=False,server_default="0"))
        b.add_column(sa.Column("duplicates_skipped",sa.Integer(),nullable=False,server_default="0"))
    op.create_table("external_record_dedup",sa.Column("id",I,primary_key=True),sa.Column("data_source_id",I,sa.ForeignKey("data_source.id",ondelete="CASCADE"),nullable=False),sa.Column("source_record_id",sa.String(500),nullable=False),sa.Column("metric_name",sa.String(100),nullable=False),sa.Column("first_seen_at",sa.DateTime(),nullable=False,server_default=sa.func.now()),sa.UniqueConstraint("data_source_id","source_record_id","metric_name",name="uq_external_record_metric"))
    op.create_index("ix_external_record_dedup_source","external_record_dedup",["data_source_id"])

def downgrade():
    op.drop_table("external_record_dedup")
    with op.batch_alter_table("data_source_runtime_state") as b:
        for name in ("duplicates_skipped","records_fetched","pages_fetched","failed_page","successful_pages","requested_pages","current_window_end","current_window_start","last_success_watermark"):b.drop_column(name)
