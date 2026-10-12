from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Enterprise
from app.schemas.scenario import ScenarioCreate, ScenarioRead, ScenarioVersionCreate, ScenarioVersionRead
from app.services import scenario_service

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

@router.post("", response_model=ScenarioRead, status_code=201)
def create(data: ScenarioCreate, db: Session = Depends(get_db)):
    if not db.get(Enterprise, data.enterprise_id): raise HTTPException(404, "enterprise not found")
    try: return scenario_service.create_scenario(db, data)
    except Exception as e:
        db.rollback(); raise HTTPException(400, str(e))

@router.get("", response_model=list[ScenarioRead])
def list_all(enterprise_id: int | None = None, db: Session = Depends(get_db)):
    return scenario_service.list_scenarios(db, enterprise_id)

@router.get("/{scenario_id}", response_model=ScenarioRead)
def get_one(scenario_id: int, db: Session = Depends(get_db)):
    obj = scenario_service.get_scenario(db, scenario_id)
    if not obj: raise HTTPException(404, "scenario not found")
    return obj

@router.post("/{scenario_id}/versions",response_model=ScenarioVersionRead,status_code=201)
def new_version(scenario_id:int,data:ScenarioVersionCreate,db:Session=Depends(get_db)):
    scenario=scenario_service.get_scenario(db,scenario_id)
    if not scenario:raise HTTPException(404,"scenario not found")
    try:return scenario_service.create_version(db,scenario,data)
    except ValueError as exc:db.rollback();raise HTTPException(400,str(exc))

@router.get("/{scenario_id}/versions",response_model=list[ScenarioVersionRead])
def versions(scenario_id:int,db:Session=Depends(get_db)):
    if not scenario_service.get_scenario(db,scenario_id):raise HTTPException(404,"scenario not found")
    return scenario_service.list_versions(db,scenario_id)

@router.get("/{scenario_id}/versions/{version_id}",response_model=ScenarioVersionRead)
def version(scenario_id:int,version_id:int,db:Session=Depends(get_db)):
    obj=scenario_service.get_version(db,version_id)
    if not obj or obj.scenario_id!=scenario_id:raise HTTPException(404,"scenario version not found")
    return obj
