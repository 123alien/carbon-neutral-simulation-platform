from app.models import PathRecommendation,PathRecommendationRun
from app.schemas.scenario import ScenarioCreate
from app.services import scenario_service

PROFILE_TYPES={"ECONOMIC":"ECONOMIC","REDUCTION":"REDUCTION","BALANCED":"BALANCED"}
def convert(db,recommendation_id,request):
    recommendation=db.get(PathRecommendation,recommendation_id)
    if recommendation is None:raise LookupError("recommendation path not found")
    run=db.get(PathRecommendationRun,recommendation.run_id)
    measures=[]
    for item in recommendation.measures_json:
        params=dict(item.get("parameters",{}))
        if item.get("investment") is not None:params.setdefault("capex",item["investment"])
        measures.append({"measure_type":item["type"],"start_year":request.start_year,"end_year":request.end_year,"parameters_json":params})
    data=ScenarioCreate(enterprise_id=run.enterprise_id,name=request.name,description=request.description,base_year=request.base_year,start_year=request.start_year,end_year=request.end_year,target_peak_year=request.target_peak_year,target_neutral_year=request.target_neutral_year,baseline_growth_json={},status="DRAFT",scenario_type=PROFILE_TYPES.get(recommendation.profile,"CUSTOM"),measures=measures)
    scenario=scenario_service.create_scenario(db,data);version=scenario_service.get_version(db,scenario.current_version_id)
    provenance=run.input_snapshot_json.get('provenance')
    if provenance:
        version.parameter_snapshot_json={**version.parameter_snapshot_json,'site_id':provenance['site_id'],'input_provenance':provenance,'unified_baseline':run.input_snapshot_json.get('unified_baseline')}
    version.source_recommendation_id=recommendation.id;db.commit();return scenario_service.get_scenario(db,scenario.id)
