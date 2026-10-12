from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models import Scenario, ScenarioMeasure, ScenarioVersion
from app.schemas.scenario import ScenarioCreate

def _snapshot(scenario, measures=None):
    measures=measures if measures is not None else scenario.measures
    return {"enterprise_id":scenario.enterprise_id,"name":scenario.name,"description":scenario.description,"base_year":scenario.base_year,"start_year":scenario.start_year,"end_year":scenario.end_year,"target_peak_year":scenario.target_peak_year,"target_neutral_year":scenario.target_neutral_year,"baseline_growth_json":scenario.baseline_growth_json,"status":scenario.status,"scenario_type":scenario.scenario_type,"measures":[{"measure_type":m.measure_type,"start_year":m.start_year,"end_year":m.end_year,"parameters_json":m.parameters_json} for m in measures]}

def _add_version(db,scenario,snapshot,source_recommendation_id=None):
    latest=db.scalar(select(ScenarioVersion.version_number).where(ScenarioVersion.scenario_id==scenario.id).order_by(ScenarioVersion.version_number.desc())) or 0
    version=ScenarioVersion(scenario_id=scenario.id,version_number=latest+1,scenario_type=snapshot.get("scenario_type","CUSTOM"),parameter_snapshot_json=snapshot,source_recommendation_id=source_recommendation_id);db.add(version);db.flush();scenario.current_version_id=version.id;return version

def create_scenario(db: Session, data: ScenarioCreate) -> Scenario:
    payload = data.model_dump(exclude={"measures"})
    scenario = Scenario(**payload)
    db.add(scenario); db.flush()
    for m in data.measures:
        db.add(ScenarioMeasure(scenario_id=scenario.id, **m.model_dump()))
    db.flush();loaded=get_scenario(db,scenario.id);_add_version(db,scenario,_snapshot(loaded))
    db.commit()
    return get_scenario(db, scenario.id)

def get_scenario(db: Session, scenario_id: int) -> Scenario | None:
    stmt = select(Scenario).options(selectinload(Scenario.measures)).where(Scenario.id == scenario_id)
    return db.scalars(stmt).first()

def list_scenarios(db: Session, enterprise_id: int | None = None) -> list[Scenario]:
    stmt = select(Scenario).options(selectinload(Scenario.measures))
    if enterprise_id is not None:
        stmt = stmt.where(Scenario.enterprise_id == enterprise_id)
    return list(db.scalars(stmt.order_by(Scenario.id.desc())).all())

def create_version(db,scenario,data,source_recommendation_id=None):
    if scenario.current_version_id:
        current=db.get(ScenarioVersion,scenario.current_version_id)
        context=(current.parameter_snapshot_json or {}).get("experiment_context") if current else None
        if isinstance(context,dict) and context.get("locked") is True:
            raise ValueError("immutable experiment baseline cannot be superseded; create a separate scenario and compare_to this baseline version")
    experiment_context=data.experiment_context
    values=data.model_dump(exclude={"measures","experiment_context"},exclude_none=True)
    if values.get("name") is None:values.pop("name",None)
    for key,value in values.items():setattr(scenario,key,value)
    for measure in list(scenario.measures):db.delete(measure)
    db.flush()
    for item in data.measures:db.add(ScenarioMeasure(scenario_id=scenario.id,**item.model_dump()))
    db.flush();db.expire(scenario,["measures"]);scenario=get_scenario(db,scenario.id);snapshot=_snapshot(scenario)
    if experiment_context is not None:snapshot["experiment_context"]=experiment_context
    version=_add_version(db,scenario,snapshot,source_recommendation_id);db.commit();db.refresh(version);return version

def list_versions(db,scenario_id):return list(db.scalars(select(ScenarioVersion).where(ScenarioVersion.scenario_id==scenario_id).order_by(ScenarioVersion.version_number)).all())
def get_version(db,version_id):return db.get(ScenarioVersion,version_id)
def ensure_version(db,scenario):
    if scenario.current_version_id:
        version=db.get(ScenarioVersion,scenario.current_version_id)
        if version:return version
    version=_add_version(db,scenario,_snapshot(scenario));db.commit();db.refresh(version);return version
