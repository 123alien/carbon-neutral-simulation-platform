"""Camera GIS anchors for cross-camera trajectory adaptation."""
from alembic import op
import sqlalchemy as sa

revision="021_camera_spatial_mapping";down_revision="020_long_term_path";branch_labels=None;depends_on=None

def upgrade():
    op.create_table("camera_spatial_mapping",
        sa.Column("id",sa.BigInteger().with_variant(sa.Integer(),"sqlite"),primary_key=True,autoincrement=True),
        sa.Column("site_id",sa.BigInteger(),sa.ForeignKey("site.id",ondelete="RESTRICT"),nullable=False),
        sa.Column("building_id",sa.BigInteger(),sa.ForeignKey("building.id",ondelete="RESTRICT")),
        sa.Column("campus_id",sa.String(100),nullable=False),sa.Column("camera_id",sa.String(200),nullable=False),
        sa.Column("floor_id",sa.String(200)),sa.Column("area_id",sa.String(200)),
        sa.Column("longitude",sa.Float(),nullable=False),sa.Column("latitude",sa.Float(),nullable=False),
        sa.Column("anchor_source",sa.String(50),nullable=False,server_default="CAMERA_LOCATION"),
        sa.Column("status",sa.String(30),nullable=False,server_default="ACTIVE"),sa.Column("metadata_json",sa.JSON(),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False),
        sa.UniqueConstraint("campus_id","camera_id",name="uq_camera_spatial_campus_camera"))
    for name in ("site_id","building_id","campus_id","camera_id","floor_id","area_id"):
        op.create_index(f"ix_camera_spatial_mapping_{name}","camera_spatial_mapping",[name])

def downgrade():
    for name in reversed(("site_id","building_id","campus_id","camera_id","floor_id","area_id")):
        op.drop_index(f"ix_camera_spatial_mapping_{name}",table_name="camera_spatial_mapping")
    op.drop_table("camera_spatial_mapping")
