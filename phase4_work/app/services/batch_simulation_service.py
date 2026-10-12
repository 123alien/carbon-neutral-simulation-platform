from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Scenario,ScenarioVersion,SimulationBatch,SimulationBatchItem
from app.schemas.hourly import HourlySimulationRunRequest
from app.services.hourly_simulation_service import run_hourly_simulation
from app.services.carbon_market_analysis_service import market_snapshot
from app.market_analysis import CarbonCostEngine

METRIC_KEYS=["cumulative_carbon_emission_t","cumulative_carbon_reduction_t","reduction_rate","total_grid_power_kwh","renewable_generation_kwh","renewable_self_consumption_rate","storage_charge_kwh","storage_discharge_kwh","total_electricity_cost","investment","payback_years","target_satisfaction","max_energy_balance_error_kwh"]

def _investment(snapshot):return sum(float(item.get("parameters_json",{}).get("capex",item.get("investment",0)) or 0) for item in snapshot.get("measures",[]))
def _response(db,batch):
    items=list(db.scalars(select(SimulationBatchItem).where(SimulationBatchItem.batch_id==batch.id).order_by(SimulationBatchItem.id)).all())
    return {"id":batch.id,"enterprise_id":batch.enterprise_id,"baseline_scenario_version_id":batch.baseline_scenario_version_id,"status":batch.status,"request_snapshot_json":batch.request_snapshot_json,"comparison_json":batch.comparison_json,"created_at":batch.created_at,"finished_at":batch.finished_at,"items":items}
def run_batch(db:Session,request):
    ids=list(dict.fromkeys(request.scenario_version_ids))
    if request.baseline_scenario_version_id not in ids:raise ValueError("baseline version must be included in scenario_version_ids")
    versions=[]
    for version_id in ids:
        version=db.get(ScenarioVersion,version_id)
        if version is None:raise LookupError(f"scenario version not found: {version_id}")
        scenario=db.get(Scenario,version.scenario_id)
        if scenario.enterprise_id!=request.enterprise_id:raise ValueError("all scenario versions must belong to the batch enterprise")
        versions.append((version,scenario))
    batch=SimulationBatch(enterprise_id=request.enterprise_id,baseline_scenario_version_id=request.baseline_scenario_version_id,status="RUNNING",request_snapshot_json=request.model_dump());db.add(batch);db.flush()
    items={}
    for version,_ in versions:
        item=SimulationBatchItem(batch_id=batch.id,scenario_version_id=version.id,status="PENDING");db.add(item);items[version.id]=item
    db.commit()
    raw={}
    for version,scenario in versions:
        item=items[version.id]
        try:
            task,results,summary=run_hourly_simulation(db,HourlySimulationRunRequest(site_id=getattr(request,'site_id',None),scenario_id=scenario.id,scenario_version_id=version.id,year=request.year,electricity_price_per_kwh=request.electricity_price_per_kwh,feed_in_tariff_per_kwh=request.feed_in_tariff_per_kwh,store_hourly_results=request.store_hourly_results))
            renewable=summary.renewable_generation_kwh;self_use=summary.pv_self_use_kwh+summary.wind_self_use_kwh
            raw[version.id]={"cumulative_carbon_emission_t":summary.carbon_emission_t,"total_grid_power_kwh":summary.grid_power_kwh,"renewable_generation_kwh":renewable,"renewable_self_consumption_rate":self_use/renewable if renewable else 0,"storage_charge_kwh":summary.storage_charge_kwh,"storage_discharge_kwh":summary.storage_discharge_kwh,"total_electricity_cost":summary.electricity_cost,"investment":_investment(version.parameter_snapshot_json),"max_energy_balance_error_kwh":max(abs(result.energy_balance_error_kwh) for result in results),"task_id":task.id,"scenario_type":version.scenario_type,"scenario_version_number":version.version_number}
            market=market_snapshot(db,version.id)
            if market:raw[version.id]["carbon_market_result"]=CarbonCostEngine.calculate(summary.carbon_emission_t,market)
            item.task_id=task.id;item.status="SUCCESS"
        except Exception as exc:
            db.rollback();item=db.get(SimulationBatchItem,item.id);item.status="FAILED";item.error_message=str(exc)
        db.commit()
    baseline=raw.get(request.baseline_scenario_version_id)
    if baseline is None:batch=db.get(SimulationBatch,batch.id);batch.status="FAILED";batch.finished_at=datetime.utcnow();db.commit();return _response(db,batch)
    for version,_ in versions:
        if version.id not in raw:continue
        metrics=raw[version.id];reduction=baseline["cumulative_carbon_emission_t"]-metrics["cumulative_carbon_emission_t"];metrics["cumulative_carbon_reduction_t"]=reduction;metrics["reduction_rate"]=reduction/baseline["cumulative_carbon_emission_t"] if baseline["cumulative_carbon_emission_t"] else 0
        saving=baseline["total_electricity_cost"]-metrics["total_electricity_cost"];metrics["payback_years"]=metrics["investment"]/saving if metrics["investment"] and saving>0 else None
        snapshot=version.parameter_snapshot_json;neutral=snapshot.get("target_neutral_year");peak=snapshot.get("target_peak_year");targets=[]
        if neutral:targets.append(min(max(metrics["reduction_rate"],0)*max(neutral-request.year,1),1))
        if peak:targets.append(1 if reduction>=0 and request.year<=peak else max(metrics["reduction_rate"],0))
        metrics["target_satisfaction"]=sum(targets)/len(targets) if targets else max(metrics["reduction_rate"],0)
    comparison=[]
    for version,_ in versions:
        if version.id not in raw:continue
        metrics=raw[version.id]
        deltas={};rates={}
        for key in METRIC_KEYS:
            value=metrics.get(key);base=baseline.get(key)
            if isinstance(value,(int,float)) and isinstance(base,(int,float)):
                deltas[key]=value-base;rates[key]=(value-base)/abs(base) if base else None
        metrics["baseline_delta"]=deltas;metrics["baseline_change_rate"]=rates
        item=db.get(SimulationBatchItem,items[version.id].id);item.metrics_json=metrics;comparison.append({"scenario_version_id":version.id,**metrics})
    batch=db.get(SimulationBatch,batch.id);batch.status="SUCCESS" if len(comparison)==len(versions) else "PARTIAL";batch.comparison_json={"baseline_scenario_version_id":request.baseline_scenario_version_id,"metrics":METRIC_KEYS,"items":comparison};batch.finished_at=datetime.utcnow();db.commit();db.refresh(batch);return _response(db,batch)
def get_batch(db,batch_id):
    batch=db.get(SimulationBatch,batch_id)
    if batch is None:raise LookupError("simulation batch not found")
    return _response(db,batch)
def list_batches(db,enterprise_id=None,limit=50):
    stmt=select(SimulationBatch)
    if enterprise_id is not None:stmt=stmt.where(SimulationBatch.enterprise_id==enterprise_id)
    return [_response(db,batch) for batch in db.scalars(stmt.order_by(SimulationBatch.created_at.desc(),SimulationBatch.id.desc()).limit(limit)).all()]
