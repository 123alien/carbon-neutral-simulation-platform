"""Park-centered data source bindings and file data nature."""
from alembic import op
import sqlalchemy as sa

revision="019_park_centered_data_sources";down_revision="018_p3_5_7";branch_labels=None;depends_on=None

def upgrade():
    with op.batch_alter_table("data_source") as b:
        b.add_column(sa.Column("site_id",sa.BigInteger(),nullable=True))
        b.add_column(sa.Column("building_id",sa.BigInteger(),nullable=True))
        b.add_column(sa.Column("device_id",sa.BigInteger(),nullable=True))
        b.add_column(sa.Column("metering_point_id",sa.BigInteger(),nullable=True))
        b.add_column(sa.Column("data_nature",sa.String(30),nullable=True))
        b.create_foreign_key("fk_data_source_site","site",["site_id"],["id"],ondelete="RESTRICT")
        b.create_foreign_key("fk_data_source_building","building",["building_id"],["id"],ondelete="RESTRICT")
        b.create_foreign_key("fk_data_source_device","device",["device_id"],["id"],ondelete="RESTRICT")
        b.create_foreign_key("fk_data_source_metering_point","metering_point",["metering_point_id"],["id"],ondelete="RESTRICT")
        for name in ("site_id","building_id","device_id","metering_point_id","data_nature"):b.create_index(f"ix_data_source_{name}",[name])

def downgrade():
    with op.batch_alter_table("data_source") as b:
        for name in ("data_nature","metering_point_id","device_id","building_id","site_id"):
            b.drop_index(f"ix_data_source_{name}")
            if name!="data_nature":b.drop_constraint(f"fk_data_source_{'metering_point' if name=='metering_point_id' else name[:-3]}",type_="foreignkey")
            b.drop_column(name)
