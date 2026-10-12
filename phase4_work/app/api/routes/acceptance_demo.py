from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.acceptance_demo_service import regional_summary, standard_validation, telemetry

router=APIRouter(prefix="/acceptance-demo",tags=["acceptance-demo"])

@router.get("/telemetry/{kind}")
def demo_telemetry(kind:str,at:datetime|None=None):
    try:return telemetry(kind,at)
    except ValueError as exc:raise HTTPException(400,str(exc))

@router.get("/accounting-standard")
def accounting_standard(site_type:str="CAMPUS"):return standard_validation(site_type)

@router.get("/regional-carbon")
def region(enterprise_id:int,db:Session=Depends(get_db)):return regional_summary(db,enterprise_id)
