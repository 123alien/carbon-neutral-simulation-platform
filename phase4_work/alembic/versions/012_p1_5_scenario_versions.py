"""P1-5 immutable scenario versions and isolated simulation batches."""
from alembic import op
import sqlalchemy as sa
revision="012_p1_5";down_revision="011_p1_4";branch_labels=None;depends_on=None
id_type=sa.BigInteger().with_variant(sa.Integer(),"sqlite")
def upgrade():
    op.add_column("scenario",sa.Column("scenario_type",sa.String(30),nullable=False,server_default="CUSTOM"));op.add_column("scenario",sa.Column("current_version_id",sa.BigInteger(),nullable=True))
    op.create_table("scenario_version",sa.Column("id",id_type,primary_key=True,autoincrement=True),sa.Column("scenario_id",id_type,sa.ForeignKey("scenario.id",ondelete="CASCADE"),nullable=False),sa.Column("version_number",sa.Integer(),nullable=False),sa.Column("scenario_type",sa.String(30),nullable=False),sa.Column("parameter_snapshot_json",sa.JSON(),nullable=False),sa.Column("source_recommendation_id",id_type,sa.ForeignKey("path_recommendation.id",ondelete="SET NULL")),sa.Column("created_at",sa.DateTime()),sa.UniqueConstraint("scenario_id","version_number",name="uq_scenario_version"));op.create_index("ix_scenario_version_scenario","scenario_version",["scenario_id"])
    with op.batch_alter_table("simulation_task") as batch:
        batch.add_column(sa.Column("scenario_version_id",id_type,nullable=True));batch.create_foreign_key("fk_task_scenario_version","scenario_version",["scenario_version_id"],["id"],ondelete="RESTRICT");batch.create_index("ix_task_scenario_version",["scenario_version_id"])
    op.create_table("simulation_batch",sa.Column("id",id_type,primary_key=True,autoincrement=True),sa.Column("enterprise_id",id_type,sa.ForeignKey("enterprise.id",ondelete="CASCADE"),nullable=False),sa.Column("baseline_scenario_version_id",id_type,sa.ForeignKey("scenario_version.id",ondelete="RESTRICT"),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("request_snapshot_json",sa.JSON(),nullable=False),sa.Column("comparison_json",sa.JSON()),sa.Column("created_at",sa.DateTime()),sa.Column("finished_at",sa.DateTime()));op.create_index("ix_batch_enterprise","simulation_batch",["enterprise_id"])
    op.create_table("simulation_batch_item",sa.Column("id",id_type,primary_key=True,autoincrement=True),sa.Column("batch_id",id_type,sa.ForeignKey("simulation_batch.id",ondelete="CASCADE"),nullable=False),sa.Column("scenario_version_id",id_type,sa.ForeignKey("scenario_version.id",ondelete="RESTRICT"),nullable=False),sa.Column("task_id",id_type,sa.ForeignKey("simulation_task.id",ondelete="SET NULL")),sa.Column("status",sa.String(30),nullable=False),sa.Column("metrics_json",sa.JSON()),sa.Column("error_message",sa.Text()),sa.UniqueConstraint("batch_id","scenario_version_id",name="uq_batch_version"));op.create_index("ix_batch_item_batch","simulation_batch_item",["batch_id"])
def downgrade():
    op.drop_table("simulation_batch_item");op.drop_table("simulation_batch")
    with op.batch_alter_table("simulation_task") as batch:
        batch.drop_index("ix_task_scenario_version");batch.drop_constraint("fk_task_scenario_version",type_="foreignkey");batch.drop_column("scenario_version_id")
    op.drop_table("scenario_version");op.drop_column("scenario","current_version_id");op.drop_column("scenario","scenario_type")
