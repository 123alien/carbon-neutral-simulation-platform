from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Enterprise, SimulationTask, SimulationHourResult
from app.services.scenario_service import get_scenario, get_version, ensure_version
from app.services.energy_service import resolve_emission_factor, list_load_points
from app.simulation.hourly import HourlyInput, HourlySimulationEngine
from app.providers import DatabaseWeatherProvider, DatabaseElectricityPriceProvider, DatabaseGridEmissionFactorProvider
from app.services.green_power_service import GreenPowerService
from app.simulation.green_power import GreenPowerAllocator
from app.services.carbon_market_analysis_service import market_snapshot


def _hourly_measure_config(scenario) -> dict:
    config: dict = {}
    for m in scenario.measures:
        p = dict(m.parameters_json or {})
        p.update({"start_year": m.start_year, "end_year": m.end_year})
        if m.measure_type == "PV":
            config["pv"] = p
        elif m.measure_type == "HVAC":
            config["hvac"] = p
        elif m.measure_type == "LIGHTING":
            config["lighting"] = p
        elif m.measure_type == "STORAGE":
            config["storage"] = p
        elif m.measure_type == "WIND":
            config["wind"] = p
        elif m.measure_type in {"EV_CHARGER", "CHARGING"}:
            config["ev_charger"] = p
        elif m.measure_type == "GREEN_POWER":
            config["green_power"] = p
    return config

def _snapshot_measure_config(snapshot):
    class Item:
        pass
    items=[]
    for raw in snapshot.get("measures",[]):
        item=Item()
        for key,value in raw.items():setattr(item,key,value)
        items.append(item)
    holder=Item();holder.measures=items
    return _hourly_measure_config(holder)


def run_hourly_simulation(db: Session, req):
    scenario = get_scenario(db, req.scenario_id)
    if scenario is None:
        raise LookupError("scenario not found")
    enterprise = db.get(Enterprise, scenario.enterprise_id)
    if enterprise is None:
        raise LookupError("enterprise not found")
    version=get_version(db,req.scenario_version_id) if getattr(req,"scenario_version_id",None) else ensure_version(db,scenario)
    if version is None or version.scenario_id!=scenario.id:raise ValueError("scenario version does not belong to scenario")
    from app.services.campus_simulation_input import resolve_site
    configured_site=version.parameter_snapshot_json.get('site_id')
    requested_site=getattr(req,'site_id',None)
    if configured_site and requested_site and configured_site!=requested_site:raise ValueError('场景与当前园区不一致')
    site=resolve_site(db,enterprise.id,requested_site or configured_site)
    if site and site.code=='HBUE':return _run_campus(db,req,scenario,version,site)
    rows = list_load_points(db, enterprise.id, req.year)
    def utc_naive(value):return value.astimezone(timezone.utc).replace(tzinfo=None) if value and value.tzinfo else value
    start_time,end_time=utc_naive(getattr(req,"start_time",None)),utc_naive(getattr(req,"end_time",None))
    if start_time is not None:rows=[row for row in rows if row.timestamp>=start_time]
    if end_time is not None:rows=[row for row in rows if row.timestamp<end_time]
    if not rows:
        raise ValueError(f"no hourly load data found for enterprise={enterprise.id}, year={req.year}")

    temporary_measures=getattr(req,"temporary_measures",None)
    config = _hourly_measure_config(type("TemporaryScenario",(),{"measures":temporary_measures})()) if temporary_measures is not None else _snapshot_measure_config(version.parameter_snapshot_json)
    range_end = rows[-1].timestamp + timedelta(hours=1)
    weather_provider = DatabaseWeatherProvider(db,getattr(req,"weather_site_id",None))
    observations = weather_provider.get_hourly(enterprise.id, rows[0].timestamp, range_end)
    weather_by_timestamp = {point.timestamp: point for point in observations}
    prices = DatabaseElectricityPriceProvider(db).get_hourly(enterprise.id, rows[0].timestamp, range_end)
    dynamic_factors = DatabaseGridEmissionFactorProvider(db).get_hourly(enterprise.region or "", rows[0].timestamp, range_end)
    ef = resolve_emission_factor(db, enterprise.region, req.year, "electricity")
    if ef is None and any(row.timestamp not in dynamic_factors for row in rows):
        raise ValueError(f"electricity emission factor not found for {req.year} and dynamic coverage is incomplete")
    if ef is not None and ef.unit.lower().replace(" ", "") != "kgco2/kwh":
        raise ValueError(f"electricity emission factor unit mismatch: {ef.unit}; expected kgCO2/kWh")
    green_config=config.get("green_power")
    if green_config and req.year>=int(green_config.get("start_year",req.year)) and (green_config.get("end_year") is None or req.year<=int(green_config["end_year"])):
        green_allocator=GreenPowerAllocator([{"start_at":rows[0].timestamp,"end_at":range_end,"purchase_share":green_config.get("purchase_share"),"purchase_kwh":green_config.get("purchase_kwh"),"emission_factor_kg_per_kwh":green_config.get("emission_factor_kg_per_kwh",0),"premium_per_kwh":green_config.get("premium_per_kwh",0)}]);contract_count=1
    else:
        green_allocator, contract_count = GreenPowerService.allocator(db, enterprise.id)
    task = SimulationTask(
        scenario_id=scenario.id,
        scenario_version_id=version.id,
        status="RUNNING",
        carbon_market_snapshot_json=market_snapshot(db,version.id),
        risk_parameter_snapshot_json=version.risk_parameter_snapshot_json,
        parameter_snapshot_json={
            "simulation_mode": "HOURLY",
            "year": req.year,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "enterprise_id": enterprise.id,
            "electricity_factor": float(ef.factor) if ef else None,
            "electricity_factor_source": ef.source if ef else None,
            "dynamic_price_points": len(prices),
            "dynamic_grid_factor_points": len(dynamic_factors),
            "green_power_contracts": contract_count,
            "measures": config,
            "temporary_config": temporary_measures is not None,
            "scenario_version_id":version.id,
            "scenario_version":version.parameter_snapshot_json,
            "carbon_market":market_snapshot(db,version.id),
            "profile_points": len(rows),
            "weather_provider": "database" if observations else "load_timeseries_fallback",
            "weather_site_id": weather_provider.site_id,
            "weather_points": len(observations),
        },
        started_at=datetime.utcnow(),
    )
    db.add(task); db.commit(); db.refresh(task)

    try:
        engine = HourlySimulationEngine(
            electricity_factor_kg_per_kwh=float(ef.factor) if ef else 0.0,
            electricity_price_per_kwh=req.electricity_price_per_kwh,
            feed_in_tariff_per_kwh=req.feed_in_tariff_per_kwh,
        )
        inputs = []
        for r in rows:
            weather = weather_by_timestamp.get(r.timestamp)
            price = prices.get(r.timestamp)
            inputs.append(HourlyInput(
                timestamp=r.timestamp,
                load_kwh=float(r.load_kwh),
                irradiation_wm2=float(weather.ghi_w_m2 if weather else (r.irradiation_wm2 or 0)),
                temperature_c=weather.temperature_c if weather else r.temperature_c,
                humidity_pct=weather.humidity_pct if weather else r.humidity_pct,
                purchase_price_per_kwh=price.purchase_price_per_kwh if price else None,
                feed_in_tariff_per_kwh=price.feed_in_tariff_per_kwh if price else None,
                grid_emission_factor_kg_per_kwh=dynamic_factors.get(r.timestamp),
                wind_speed_m_s=weather.wind_speed_m_s if weather else None,
            ))
        results, summary = engine.run(inputs, config, green_allocator)
        if req.store_hourly_results:
            for r in results:
                db.add(SimulationHourResult(
                    task_id=task.id, scenario_id=scenario.id, **r.to_dict()
                ))
        task.summary_json = {
            "simulation_mode": "HOURLY",
            **summary.__dict__,
        }
        task.status = "SUCCESS"
        task.finished_at = datetime.utcnow()
        db.commit(); db.refresh(task)
        return task, results, summary
    except Exception as exc:
        db.rollback()
        task = db.get(SimulationTask, task.id)
        task.status = "FAILED"
        task.error_message = str(exc)
        task.finished_at = datetime.utcnow()
        db.commit(); db.refresh(task)
        raise


def get_hourly_task_result(db: Session, task_id: int):
    task = db.get(SimulationTask, task_id)
    if task is None:
        return None, []
    rows = list(db.scalars(
        select(SimulationHourResult)
        .where(SimulationHourResult.task_id == task_id)
        .order_by(SimulationHourResult.timestamp)
    ).all())
    return task, rows

def _run_campus(db,req,scenario,version,site):
    from app.services.campus_simulation_input import build,combine,freeze,restore
    frozen=version.parameter_snapshot_json.get('unified_baseline')
    if frozen:
        if frozen['provenance']['year']!=req.year or frozen['provenance']['site_id']!=site.id:raise ValueError('场景已冻结的园区或年度与当前请求不一致，请创建新的年度场景')
        points=restore(frozen);base=frozen['existing_config'];provenance=frozen['provenance']
    else:
        points,base,provenance=build(db,site,req.year)
        frozen=freeze(points,base,provenance,req.electricity_price_per_kwh,req.feed_in_tariff_per_kwh)
    temporary=getattr(req,'temporary_measures',None)
    changes=_hourly_measure_config(type('S',(),{'measures':temporary})()) if temporary is not None else _snapshot_measure_config(version.parameter_snapshot_json)
    config=combine(base,changes)
    def normalize(t):return t.astimezone(timezone.utc).replace(tzinfo=None) if t.tzinfo else t
    start=getattr(req,'start_time',None);end=getattr(req,'end_time',None)
    points=[p for p in points if (start is None or normalize(p.timestamp)>=normalize(start)) and (end is None or normalize(p.timestamp)<normalize(end))]
    if not points:raise ValueError('所选园区在该时间范围内无仿真输入')
    if start and normalize(start)>normalize(datetime(req.year,1,1,tzinfo=points[0].timestamp.tzinfo)):
        raise ValueError('校园统一基准需从年初开始，以保持储能连续状态；请清除开始时间或选择年初')
    green=changes.get('green_power');allocator=None
    if green and HourlySimulationEngine._active(green,points[0].timestamp):
        allocator=GreenPowerAllocator([{'start_at':points[0].timestamp,'end_at':points[-1].timestamp+timedelta(hours=1),'purchase_share':green.get('purchase_share'),'purchase_kwh':green.get('purchase_kwh'),'emission_factor_kg_per_kwh':green.get('emission_factor_kg_per_kwh',0),'premium_per_kwh':green.get('premium_per_kwh',0)}])
    results,summary=HourlySimulationEngine(.5703,req.electricity_price_per_kwh,req.feed_in_tariff_per_kwh).run(points,config,allocator)
    task=SimulationTask(scenario_id=scenario.id,scenario_version_id=version.id,status='SUCCESS',started_at=datetime.utcnow(),finished_at=datetime.utcnow(),carbon_market_snapshot_json=market_snapshot(db,version.id),risk_parameter_snapshot_json=version.risk_parameter_snapshot_json,parameter_snapshot_json={'simulation_mode':'HOURLY','year':req.year,'enterprise_id':site.enterprise_id,'site_id':site.id,'provenance':provenance,'unified_baseline':frozen,'measures':config,'scenario_version':version.parameter_snapshot_json},summary_json={'simulation_mode':'HOURLY',**summary.__dict__,'provenance':provenance})
    db.add(task);db.flush()
    if req.store_hourly_results:
        for result in results:
            data=result.to_dict();data['timestamp']=data['timestamp'].astimezone(timezone.utc).replace(tzinfo=None)
            db.add(SimulationHourResult(task_id=task.id,scenario_id=scenario.id,**data))
    db.commit();db.refresh(task);return task,results,summary
