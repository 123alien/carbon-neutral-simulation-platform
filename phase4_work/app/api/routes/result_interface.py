from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.schemas.result_interface import (
    BuildingResultPage, CampusOverviewResult, CarbonMarketResultInterface, SimulationResultInterface,
)
from app.services import result_interface_service as service

router = APIRouter(prefix="/result-interface", tags=["unified-result-interface"])

@router.get('/campuses/{site_id}/simulation-baseline')
def simulation_baseline(site_id:int,year:int,db:Session=Depends(get_db)):
    from app.services.campus_simulation_input import resolve_site,build
    from app.models import Site
    site=db.get(Site,site_id)
    if site is None:raise HTTPException(404,'园区不存在')
    if site.code!='HBUE':raise HTTPException(400,'该接口仅用于校园统一示范基准')
    try:points,config,provenance=build(db,site,year)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    loads=[p.load_kwh+p.existing_ev_kwh for p in points]
    n=len(points)
    return {'provenance':provenance,'load':dict(total_electricity_kwh=sum(loads),peak_load_kw=max(loads),average_load_kw=sum(loads)/n,minimum_load_kw=min(loads),observed_points=n,expected_points=n,missing_points=0,completeness_rate=1,quality='示范仿真数据'),
        'weather':dict(average_temperature_c=sum(p.temperature_c for p in points)/n,peak_ghi_w_m2=max(p.irradiation_wm2 for p in points),total_ghi_wh_m2=sum(p.irradiation_wm2 for p in points),observed_points=n,expected_points=n,missing_points=0,completeness_rate=1,quality='示范仿真数据')}

@router.get('/campuses/{site_id}/live-demo')
def live_demo(site_id:int,history_hours:int=Query(168,ge=1,le=8784),at:datetime|None=None,db:Session=Depends(get_db)):
    from app.services.campus_live_demo_service import snapshot
    if at is not None and (at.tzinfo is None or at.year<2024 or at>datetime.now(at.tzinfo)):
        raise HTTPException(400,'快照时间必须带时区，且位于2024年至当前时间范围内')
    try:return snapshot(db,site_id,at=at,history_hours=history_hours)
    except LookupError as exc:raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc


def _call(function, *args):
    try:
        return function(*args)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/campuses/{site_id}/overview", response_model=CampusOverviewResult)
def campus_overview(site_id: int, db: Session = Depends(get_db)):
    return _call(service.campus_overview, db, site_id)


@router.get("/campuses/{site_id}/buildings", response_model=BuildingResultPage)
def building_results(site_id: int, db: Session = Depends(get_db)):
    return _call(service.building_results, db, site_id)


@router.get("/campuses/{site_id}/simulation", response_model=SimulationResultInterface)
def simulation_results(site_id: int, db: Session = Depends(get_db)):
    return _call(service.simulation_results, db, site_id)


@router.get("/campuses/{site_id}/carbon-market", response_model=CarbonMarketResultInterface)
def carbon_market_results(site_id: int, region: str | None = None, db: Session = Depends(get_db)):
    return _call(service.market_results, db, site_id, region)
