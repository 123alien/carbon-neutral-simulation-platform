from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Enterprise
from app.schemas.enterprise import EnterpriseCreate, EnterpriseUpdate

def create_enterprise(db: Session, data: EnterpriseCreate) -> Enterprise:
    obj = Enterprise(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

def list_enterprises(db: Session) -> list[Enterprise]:
    return list(db.scalars(select(Enterprise).order_by(Enterprise.id.desc())).all())

def get_enterprise(db: Session, enterprise_id: int) -> Enterprise | None:
    return db.get(Enterprise, enterprise_id)

def update_enterprise(db: Session, obj: Enterprise, data: EnterpriseUpdate) -> Enterprise:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    db.commit(); db.refresh(obj)
    return obj
