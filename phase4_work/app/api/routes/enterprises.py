from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.enterprise import EnterpriseCreate, EnterpriseUpdate, EnterpriseRead
from app.services import enterprise_service

router = APIRouter(prefix="/enterprises", tags=["enterprises"])

@router.post("", response_model=EnterpriseRead, status_code=201)
def create(data: EnterpriseCreate, db: Session = Depends(get_db)):
    return enterprise_service.create_enterprise(db, data)

@router.get("", response_model=list[EnterpriseRead])
def list_all(db: Session = Depends(get_db)):
    return enterprise_service.list_enterprises(db)

@router.get("/{enterprise_id}", response_model=EnterpriseRead)
def get_one(enterprise_id: int, db: Session = Depends(get_db)):
    obj = enterprise_service.get_enterprise(db, enterprise_id)
    if not obj: raise HTTPException(404, "enterprise not found")
    return obj

@router.patch("/{enterprise_id}", response_model=EnterpriseRead)
def update(enterprise_id: int, data: EnterpriseUpdate, db: Session = Depends(get_db)):
    obj = enterprise_service.get_enterprise(db, enterprise_id)
    if not obj: raise HTTPException(404, "enterprise not found")
    return enterprise_service.update_enterprise(db, obj, data)
