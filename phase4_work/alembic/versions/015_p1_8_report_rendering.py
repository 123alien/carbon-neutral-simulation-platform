"""P1-8 immutable snapshot report rendering artifacts."""
from alembic import op
import sqlalchemy as sa
revision="015_p1_8";down_revision="014_p1_7";branch_labels=None;depends_on=None
I=sa.BigInteger().with_variant(sa.Integer(),"sqlite")
def upgrade():
    with op.batch_alter_table("report_task") as b:
        b.add_column(sa.Column("failure_reason",sa.Text()));b.add_column(sa.Column("generated_at",sa.DateTime()))
    op.create_table("report_file",sa.Column("id",I,primary_key=True),sa.Column("report_task_id",I,sa.ForeignKey("report_task.id",ondelete="CASCADE"),nullable=False),sa.Column("format",sa.String(10),nullable=False),sa.Column("file_name",sa.String(500),nullable=False),sa.Column("storage_path",sa.String(1000),nullable=False),sa.Column("file_size",sa.BigInteger(),nullable=False),sa.Column("checksum",sa.String(64),nullable=False),sa.Column("generated_at",sa.DateTime()),sa.UniqueConstraint("report_task_id","format",name="uq_report_file_format"));op.create_index("ix_report_file_task","report_file",["report_task_id"])
def downgrade():
    op.drop_table("report_file")
    with op.batch_alter_table("report_task") as b:b.drop_column("generated_at");b.drop_column("failure_reason")
