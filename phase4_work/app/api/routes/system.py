from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import system_service as service
router=APIRouter(prefix="/system",tags=["system"])
def call(fn,*args):
    try:return fn(*args)
    except LookupError as exc:raise HTTPException(404,str(exc))
@router.get("/health")
def health(db:Session=Depends(get_db)):return service.health(db)
@router.get("/providers")
def providers(enterprise_id:int|None=None,db:Session=Depends(get_db)):return service.providers(db,enterprise_id)
@router.get("/version")
def version(db:Session=Depends(get_db)):return service.health(db)
@router.get("/data-sources")
def data_sources(enterprise_id:int|None=None,db:Session=Depends(get_db)):return service.data_sources(db,enterprise_id)
@router.get("/tasks")
def tasks(enterprise_id:int|None=None,limit:int=100,db:Session=Depends(get_db)):return service.tasks(db,enterprise_id,max(1,min(limit,200)))
@router.get("/trace")
def trace(scenario_version_id:int|None=None,data_source_id:int|None=None,db:Session=Depends(get_db)):return call(service.trace,db,scenario_version_id,data_source_id)
@router.get("/overview")
def overview(enterprise_id:int|None=None,db:Session=Depends(get_db)):return service.overview(db,enterprise_id)
