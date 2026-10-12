"""P3-4 automatic acquisition configuration and runtime state."""
from alembic import op
import sqlalchemy as sa
revision="016_p3_4";down_revision="015_p1_8";branch_labels=None;depends_on=None
I=sa.BigInteger().with_variant(sa.Integer(),"sqlite")
def upgrade():
    with op.batch_alter_table("data_source") as b:
        b.add_column(sa.Column("collection_mode",sa.String(20),nullable=False,server_default="MANUAL"))
        b.add_column(sa.Column("schedule_enabled",sa.Boolean(),nullable=False,server_default=sa.false()))
        b.add_column(sa.Column("interval_minutes",sa.Integer()))
    op.create_table("data_source_runtime_state",sa.Column("id",I,primary_key=True),sa.Column("data_source_id",I,sa.ForeignKey("data_source.id",ondelete="CASCADE"),nullable=False,unique=True),sa.Column("runtime_status",sa.String(30),nullable=False,server_default="STOPPED"),sa.Column("connected",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("subscribed",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("last_started_at",sa.DateTime()),sa.Column("last_success_at",sa.DateTime()),sa.Column("last_failure_at",sa.DateTime()),sa.Column("next_run_at",sa.DateTime()),sa.Column("last_connected_at",sa.DateTime()),sa.Column("last_disconnected_at",sa.DateTime()),sa.Column("last_message_at",sa.DateTime()),sa.Column("last_received_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("last_persisted_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("last_rejected_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("received_count",sa.BigInteger(),nullable=False,server_default="0"),sa.Column("persisted_count",sa.BigInteger(),nullable=False,server_default="0"),sa.Column("rejected_count",sa.BigInteger(),nullable=False,server_default="0"),sa.Column("dropped_count",sa.BigInteger(),nullable=False,server_default="0"),sa.Column("reconnect_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("consecutive_failures",sa.Integer(),nullable=False,server_default="0"),sa.Column("current_topic",sa.String(500)),sa.Column("last_error",sa.Text()),sa.Column("updated_at",sa.DateTime(),nullable=False,server_default=sa.func.now()))
    op.create_index("ix_data_source_runtime_state_source","data_source_runtime_state",["data_source_id"],unique=True)
def downgrade():
    op.drop_table("data_source_runtime_state")
    with op.batch_alter_table("data_source") as b:
        b.drop_column("interval_minutes");b.drop_column("schedule_enabled");b.drop_column("collection_mode")
