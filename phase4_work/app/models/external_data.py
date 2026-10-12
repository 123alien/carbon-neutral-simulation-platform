"""External staging records; unassigned devices do not enter campus accounting."""
from datetime import datetime
from sqlalchemy import Integer, String, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class ExternalDataRecord(Base):
    __tablename__='external_data_record'
    __table_args__=(UniqueConstraint('source_type','record_kind','record_key',name='uq_external_data_record'),)
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    source_type:Mapped[str]=mapped_column(String(40),index=True)
    record_kind:Mapped[str]=mapped_column(String(20))
    record_key:Mapped[str]=mapped_column(String(200))
    payload:Mapped[dict]=mapped_column(JSON)
    collected_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
