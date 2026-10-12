from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.carbon_market import *
from app.services import carbon_market_analysis_service as service
from app.services import report_render_service
from fastapi.responses import FileResponse
router=APIRouter(tags=["carbon-market-risk-reports"])
def call(fn,*args):
    try:return fn(*args)
    except LookupError as e:raise HTTPException(404,str(e))
    except ValueError as e:raise HTTPException(400,str(e))
@router.post("/carbon-market/scenarios",response_model=CarbonMarketScenarioRead,status_code=201)
def create_scenario(data:CarbonMarketScenarioCreate,db:Session=Depends(get_db)):return call(service.create_market_scenario,db,data)
@router.get("/carbon-market/scenarios/{scenario_version_id}",response_model=CarbonMarketScenarioRead)
def get_scenario(scenario_version_id:int,db:Session=Depends(get_db)):return call(service.get_market_scenario,db,scenario_version_id)
@router.post("/carbon-market/indicators/bulk",status_code=201)
def indicators(data:CarbonMarketIndicatorBulkCreate,db:Session=Depends(get_db)):return call(service.add_indicators,db,data)
@router.get("/carbon-market/statistics")
def stats(region:str,start:datetime|None=None,end:datetime|None=None,db:Session=Depends(get_db)):return service.statistics(db,region,start,end)
@router.post("/carbon-market/assessments",response_model=CarbonCostAssessmentRead,status_code=201)
def cost(data:CarbonCostAssessmentCreate,db:Session=Depends(get_db)):return call(service.assess_cost,db,data)
@router.get("/carbon-market/assessments",response_model=list[CarbonCostAssessmentRead])
def costs(scenario_version_id:int|None=None,task_id:int|None=None,limit:int=100,db:Session=Depends(get_db)):return service.list_costs(db,scenario_version_id,task_id,max(1,min(limit,200)))
@router.get("/carbon-market/assessments/{id}",response_model=CarbonCostAssessmentRead)
def get_cost(id:int,db:Session=Depends(get_db)):return call(service.get_cost,db,id)
@router.get("/carbon-market/batches/{batch_id}/comparison")
def market_comparison(batch_id:int,db:Session=Depends(get_db)):return call(service.batch_market_comparison,db,batch_id)
@router.post("/risk-assessments",response_model=RiskAssessmentRead,status_code=201)
def risk(data:RiskAssessmentCreate,db:Session=Depends(get_db)):return call(service.assess_risk,db,data)
@router.get("/risk-assessments",response_model=list[RiskAssessmentRead])
def risks(scenario_version_id:int|None=None,simulation_task_id:int|None=None,start:datetime|None=None,end:datetime|None=None,limit:int=100,db:Session=Depends(get_db)):return service.list_risks(db,scenario_version_id,simulation_task_id,start,end,max(1,min(limit,200)))
@router.get("/risk-assessments/{id}",response_model=RiskAssessmentRead)
def get_risk(id:int,db:Session=Depends(get_db)):return call(service.get_risk,db,id)
@router.post("/reports/feasibility",response_model=FeasibilityReportRead,status_code=201)
def report(data:FeasibilityReportCreate,db:Session=Depends(get_db)):return call(service.create_report,db,data)
@router.get("/reports",response_model=list[FeasibilityReportRead])
def reports(site_id:int|None=None,scenario_version_id:int|None=None,simulation_task_id:int|None=None,status:str|None=None,start:datetime|None=None,end:datetime|None=None,limit:int=100,db:Session=Depends(get_db)):return call(service.list_reports,db,site_id,scenario_version_id,simulation_task_id,status,start,end,max(1,min(limit,200)))
@router.get("/reports/feasibility/{id}",response_model=FeasibilityReportRead)
def get_report(id:int,db:Session=Depends(get_db)):return call(service.get_report,db,id)
@router.post("/reports/{report_id}/render",response_model=list[ReportFileRead])
def render_report(report_id:int,data:ReportRenderRequest,db:Session=Depends(get_db)):return call(report_render_service.render,db,report_id,data.formats)
@router.get("/reports/{report_id}/downloads",response_model=list[ReportFileRead])
def downloads(report_id:int,db:Session=Depends(get_db)):return call(report_render_service.files,db,report_id)
def _download(report_id,fmt,db):
    row,path=call(report_render_service.file_for,db,report_id,fmt);media="application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt=="DOCX" else "application/pdf";return FileResponse(path,media_type=media,filename=row.file_name)
@router.get("/reports/{report_id}/download/docx")
def download_docx(report_id:int,db:Session=Depends(get_db)):return _download(report_id,"DOCX",db)
@router.get("/reports/{report_id}/download/pdf")
def download_pdf(report_id:int,db:Session=Depends(get_db)):return _download(report_id,"PDF",db)
