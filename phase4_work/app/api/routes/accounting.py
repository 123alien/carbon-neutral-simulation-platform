from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.accounting import OrganizationNodeCreate,OrganizationNodeRead,CarbonAccountingRunRequest,CarbonAccountingRunRead,CarbonAccountingResultRead,AccountingStatisticsResponse
from app.services import carbon_accounting_service as service
router=APIRouter(tags=["carbon-accounting"])
def _call(fn,*args):
    try:return fn(*args)
    except LookupError as exc:raise HTTPException(404,str(exc))
    except ValueError as exc:raise HTTPException(400,str(exc))
@router.post("/organizations",response_model=OrganizationNodeRead,status_code=201)
def create_org(data:OrganizationNodeCreate,db:Session=Depends(get_db)):return _call(service.create_organization,db,data)
@router.get("/organizations",response_model=list[OrganizationNodeRead])
def orgs(enterprise_id:int,db:Session=Depends(get_db)):return service.list_organizations(db,enterprise_id)
@router.post("/carbon-accounting/runs",response_model=CarbonAccountingRunRead,status_code=201)
def run(data:CarbonAccountingRunRequest,db:Session=Depends(get_db)):return _call(service.run,db,data)
@router.get("/carbon-accounting/runs",response_model=list[CarbonAccountingRunRead])
def runs(enterprise_id:int|None=None,start_time:datetime|None=None,end_time:datetime|None=None,status:str|None=None,db:Session=Depends(get_db)):return service.list_runs(db,enterprise_id,start_time,end_time,status)
@router.get("/carbon-accounting/runs/{run_id}",response_model=CarbonAccountingRunRead)
def get_run(run_id:int,db:Session=Depends(get_db)):return _call(service.get_run,db,run_id)
@router.get("/carbon-accounting/runs/{run_id}/results",response_model=list[CarbonAccountingResultRead])
def results(run_id:int,energy_type:str|None=None,scope:str|None=None,device_id:int|None=None,organization_node_id:int|None=None,start_time:datetime|None=None,end_time:datetime|None=None,db:Session=Depends(get_db)):return _call(service.results,db,run_id,energy_type,scope,device_id,organization_node_id,start_time,end_time)
@router.get("/carbon-accounting/runs/{run_id}/statistics",response_model=AccountingStatisticsResponse)
def statistics(run_id:int,granularity:str="month",dimension:str="energy",timezone_name:str=Query("UTC",alias="timezone"),energy_type:str|None=None,scope:str|None=None,organization_node_id:int|None=None,start_time:datetime|None=None,end_time:datetime|None=None,db:Session=Depends(get_db)):return _call(service.statistics,db,run_id,granularity,dimension,timezone_name,energy_type,scope,organization_node_id,start_time,end_time)
