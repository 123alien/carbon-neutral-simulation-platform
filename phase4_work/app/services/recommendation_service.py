from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Enterprise,PathRecommendation,PathRecommendationRun
from app.providers import DatabaseElectricityPriceProvider,DatabaseGridEmissionFactorProvider,DatabaseWeatherProvider
from app.recommendation import LowCarbonPathRecommendationEngine
from app.services.energy_service import list_load_points,resolve_emission_factor
from app.simulation.hourly import HourlyInput

def generate(db:Session,request):
    enterprise=db.get(Enterprise,request.enterprise_id)
    if enterprise is None:raise LookupError("enterprise not found")
    from app.services.campus_simulation_input import resolve_site,build,freeze
    site=resolve_site(db,enterprise.id,getattr(request,'site_id',None))
    if site and site.code=='HBUE':
        points,config,provenance=build(db,site,request.simulation_year)
        frozen=freeze(points,config,provenance)
        baseline,profiles=LowCarbonPathRecommendationEngine(points,.5703).recommend(request,{'year':request.simulation_year,'building_area':enterprise.building_area,'population':enterprise.population,'baseline_config':config})
        run=PathRecommendationRun(enterprise_id=enterprise.id,simulation_year=request.simulation_year,input_snapshot_json={**request.model_dump(mode='json'),'site_id':site.id,'provenance':provenance,'unified_baseline':frozen},baseline_summary_json={**baseline.__dict__,'provenance':provenance});db.add(run);db.flush()
        for profile,paths in profiles.items():
            for rank,path in enumerate(paths,1):db.add(PathRecommendation(run_id=run.id,profile=profile,rank=rank,score=path['score'],measures_json=path['measures'],reasons_json=path['reasons'],metrics_json={**path['metrics'],'score_dimensions':path['dimensions']},validation_summary_json={**path['validation'],'provenance':provenance}))
        db.commit();db.refresh(run);return response(db,run)
    rows=list_load_points(db,enterprise.id,request.simulation_year)
    if not rows:raise ValueError("hourly load data is required to validate recommendations")
    end=rows[-1].timestamp+timedelta(hours=1);weather=DatabaseWeatherProvider(db).get_hourly(enterprise.id,rows[0].timestamp,end);weather_map={item.timestamp:item for item in weather};prices=DatabaseElectricityPriceProvider(db).get_hourly(enterprise.id,rows[0].timestamp,end);factors=DatabaseGridEmissionFactorProvider(db).get_hourly(enterprise.region or "",rows[0].timestamp,end)
    annual=resolve_emission_factor(db,enterprise.region,request.simulation_year,"electricity")
    if annual is None and any(row.timestamp not in factors for row in rows):raise ValueError("electricity factor coverage is incomplete")
    fallback=float(annual.factor) if annual else 0
    points=[]
    for row in rows:
        w=weather_map.get(row.timestamp);price=prices.get(row.timestamp)
        points.append(HourlyInput(timestamp=row.timestamp,load_kwh=float(row.load_kwh),irradiation_wm2=float(w.ghi_w_m2 if w else (row.irradiation_wm2 or 0)),temperature_c=w.temperature_c if w else row.temperature_c,humidity_pct=w.humidity_pct if w else row.humidity_pct,wind_speed_m_s=w.wind_speed_m_s if w else None,purchase_price_per_kwh=price.purchase_price_per_kwh if price else None,feed_in_tariff_per_kwh=price.feed_in_tariff_per_kwh if price else None,grid_emission_factor_kg_per_kwh=factors.get(row.timestamp)))
    context={"year":request.simulation_year,"building_area":enterprise.building_area,"population":enterprise.population,"enterprise_id":enterprise.id,"baseline_scenario_version_id":3 if enterprise.id==1 and request.simulation_year==2016 else None}
    baseline,profiles=LowCarbonPathRecommendationEngine(points,fallback).recommend(request,context)
    run=PathRecommendationRun(enterprise_id=enterprise.id,simulation_year=request.simulation_year,input_snapshot_json=request.model_dump(mode="json"),baseline_summary_json=baseline.__dict__);db.add(run);db.flush()
    for profile,paths in profiles.items():
        for rank,path in enumerate(paths,1):db.add(PathRecommendation(run_id=run.id,profile=profile,rank=rank,score=path["score"],measures_json=path["measures"],reasons_json=path["reasons"],metrics_json={**path["metrics"],"score_dimensions":path["dimensions"]},validation_summary_json=path["validation"]))
    db.commit();db.refresh(run);return response(db,run)
def response(db,run):
    paths=list(db.scalars(select(PathRecommendation).where(PathRecommendation.run_id==run.id).order_by(PathRecommendation.profile,PathRecommendation.rank)).all())
    return {"id":run.id,"enterprise_id":run.enterprise_id,"simulation_year":run.simulation_year,"input_snapshot_json":run.input_snapshot_json,"baseline_summary_json":run.baseline_summary_json,"created_at":run.created_at,"recommendations":paths}
def get(db,run_id):
    run=db.get(PathRecommendationRun,run_id)
    if run is None:raise LookupError("recommendation run not found")
    return response(db,run)
def list_runs(db,enterprise_id=None,limit=50):
    stmt=select(PathRecommendationRun)
    if enterprise_id is not None:stmt=stmt.where(PathRecommendationRun.enterprise_id==enterprise_id)
    return [response(db,run) for run in db.scalars(stmt.order_by(PathRecommendationRun.created_at.desc(),PathRecommendationRun.id.desc()).limit(limit)).all()]
