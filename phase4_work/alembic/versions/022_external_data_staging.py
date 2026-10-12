"""External device discovery and observation staging, no campus assignment."""
from alembic import op
import sqlalchemy as sa
revision='022_external_data_staging'
down_revision='021_camera_spatial_mapping'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('external_data_record',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('source_type',sa.String(40),nullable=False),sa.Column('record_kind',sa.String(20),nullable=False),sa.Column('record_key',sa.String(200),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),sa.Column('collected_at',sa.DateTime(),nullable=False),sa.UniqueConstraint('source_type','record_kind','record_key',name='uq_external_data_record'))
    op.create_index('ix_external_data_record_source_type','external_data_record',['source_type'])
def downgrade():
    op.drop_index('ix_external_data_record_source_type',table_name='external_data_record')
    op.drop_table('external_data_record')
