"""P1-4 validated low-carbon path recommendations."""
from alembic import op
import sqlalchemy as sa
revision="011_p1_4";down_revision="010_p1_3";branch_labels=None;depends_on=None
id_type=sa.BigInteger().with_variant(sa.Integer(),"sqlite")
def upgrade():
    op.create_table("path_recommendation_run",sa.Column("id",id_type,primary_key=True,autoincrement=True),sa.Column("enterprise_id",id_type,sa.ForeignKey("enterprise.id",ondelete="CASCADE"),nullable=False),sa.Column("simulation_year",sa.Integer(),nullable=False),sa.Column("input_snapshot_json",sa.JSON(),nullable=False),sa.Column("baseline_summary_json",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime()));op.create_index("ix_path_run_enterprise","path_recommendation_run",["enterprise_id"])
    op.create_table("path_recommendation",sa.Column("id",id_type,primary_key=True,autoincrement=True),sa.Column("run_id",id_type,sa.ForeignKey("path_recommendation_run.id",ondelete="CASCADE"),nullable=False),sa.Column("profile",sa.String(30),nullable=False),sa.Column("rank",sa.Integer(),nullable=False),sa.Column("score",sa.Float(),nullable=False),sa.Column("measures_json",sa.JSON(),nullable=False),sa.Column("reasons_json",sa.JSON(),nullable=False),sa.Column("metrics_json",sa.JSON(),nullable=False),sa.Column("validation_summary_json",sa.JSON(),nullable=False),sa.UniqueConstraint("run_id","profile","rank",name="uq_recommendation_rank"));op.create_index("ix_path_rec_run","path_recommendation",["run_id"]);op.create_index("ix_path_rec_profile","path_recommendation",["profile"])
def downgrade():op.drop_table("path_recommendation");op.drop_table("path_recommendation_run")
