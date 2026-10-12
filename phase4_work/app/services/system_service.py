from datetime import datetime, timezone
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from app.database import engine
from app.models import (CarbonCostAssessment,DataSource,DataValidationLog,Device,DeviceMetric,ElectricityPriceTimeseries,
 GridEmissionFactorTimeseries,GreenPowerContract,PathRecommendationRun,ReportFile,ReportTask,RiskAssessmentRun,Scenario,
 ScenarioVersion,SimulationBatch,SimulationBatchItem,SimulationTask,WeatherSite,WeatherTimeseries,CarbonAccountingResult)

BACKEND_VERSION="1.0.0-alpha.11";API_VERSION="1.0";ALEMBIC_HEAD="017_p3_5_2_1"
def _revision(db):
    try:return db.execute(text("select version_num from alembic_version")).scalar()
    except Exception:db.rollback();return None
def health(db:Session):
    database_status="UP"
    try:db.execute(text("select 1"))
    except Exception:db.rollback();database_status="DOWN"
    revision=_revision(db)
    return {"application_status":"UP" if database_status=="UP" else "DEGRADED","backend_version":BACKEND_VERSION,"api_version":API_VERSION,"database_status":database_status,"database_type":engine.dialect.name,"alembic_revision":revision,"alembic_head":ALEMBIC_HEAD,"is_head":revision==ALEMBIC_HEAD,"current_time":datetime.now(timezone.utc),"uptime_seconds":None}
def _provider(db,name,model,enterprise_id=None,source_model=None):
    stmt=select(func.count(),func.min(model.timestamp),func.max(model.timestamp))
    if enterprise_id is not None and hasattr(model,"enterprise_id"):stmt=stmt.where(model.enterprise_id==enterprise_id)
    if enterprise_id is not None and model is WeatherTimeseries:stmt=stmt.join(WeatherSite,WeatherSite.id==WeatherTimeseries.site_id).where(WeatherSite.enterprise_id==enterprise_id)
    count,start,end=db.execute(stmt).one();latest=None;source=None
    if count:
        latest_stmt=select(model).order_by(model.timestamp.desc())
        if enterprise_id is not None and hasattr(model,"enterprise_id"):latest_stmt=latest_stmt.where(model.enterprise_id==enterprise_id)
        if enterprise_id is not None and model is WeatherTimeseries:latest_stmt=latest_stmt.join(WeatherSite,WeatherSite.id==WeatherTimeseries.site_id).where(WeatherSite.enterprise_id==enterprise_id)
        latest=db.scalars(latest_stmt).first();source=getattr(latest,"source",None)
    return {"provider":name,"dynamic_data_available":bool(count),"record_count":count,"latest_data_time":end,"range_start":start,"range_end":end,"source":source,"using_fallback":not bool(count)}
def providers(db:Session,enterprise_id=None):
    weather=_provider(db,"WeatherProvider",WeatherTimeseries,enterprise_id)
    price=_provider(db,"ElectricityPriceProvider",ElectricityPriceTimeseries,enterprise_id)
    grid=_provider(db,"GridEmissionFactorProvider",GridEmissionFactorTimeseries,None)
    q=select(GreenPowerContract).order_by(GreenPowerContract.end_at.desc())
    if enterprise_id is not None:q=q.where(GreenPowerContract.enterprise_id==enterprise_id)
    contracts=list(db.scalars(q).all());green={"provider":"GreenPowerService","dynamic_data_available":bool(contracts),"record_count":len(contracts),"latest_data_time":max((x.end_at for x in contracts),default=None),"range_start":min((x.start_at for x in contracts),default=None),"range_end":max((x.end_at for x in contracts),default=None),"source":next((x.source for x in contracts if x.source),None),"using_fallback":not bool(contracts)}
    return [weather,price,grid,green]
def data_sources(db:Session,enterprise_id=None):
    stmt=select(DataSource)
    if enterprise_id is not None:stmt=stmt.where(DataSource.enterprise_id==enterprise_id)
    result=[]
    for source in db.scalars(stmt.order_by(DataSource.id)).all():
        logs=list(db.scalars(select(DataValidationLog).where(DataValidationLog.data_source_id==source.id).order_by(DataValidationLog.created_at.desc())).all());errors=[x for x in logs if x.level=="ERROR"];warnings=[x for x in logs if x.level=="WARNING"]
        valid=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==source.id)) or 0;total=valid+len(errors)
        result.append({"id":source.id,"enterprise_id":source.enterprise_id,"name":source.name,"source_type":source.source_type,"status":source.status,"last_sync_at":source.last_sync_at,"last_success_at":source.last_sync_at if source.last_sync_at and not errors else None,"last_failure_at":errors[0].created_at if errors else None,"last_failure_reason":errors[0].message if errors else None,"quality_rate":valid/total if total else None,"valid_records":valid,"rejected_records":len(errors),"warning_records":len(warnings),"supports_connection_test":True,"supports_manual_sync":True})
    return result
def tasks(db:Session,enterprise_id=None,limit=100):
    scenario_ids=select(Scenario.id)
    if enterprise_id is not None:scenario_ids=scenario_ids.where(Scenario.enterprise_id==enterprise_id)
    rows=[]
    for x in db.scalars(select(SimulationTask).where(SimulationTask.scenario_id.in_(scenario_ids)).order_by(SimulationTask.id.desc()).limit(limit)).all():rows.append({"task_type":"SIMULATION","id":x.id,"status":x.status,"created_at":x.started_at,"finished_at":x.finished_at,"failure_reason":x.error_message,"scenario_version_id":x.scenario_version_id})
    q=select(PathRecommendationRun)
    if enterprise_id is not None:q=q.where(PathRecommendationRun.enterprise_id==enterprise_id)
    for x in db.scalars(q.order_by(PathRecommendationRun.id.desc()).limit(limit)).all():rows.append({"task_type":"RECOMMENDATION","id":x.id,"status":"SUCCESS","created_at":x.created_at,"finished_at":x.created_at,"failure_reason":None})
    q=select(SimulationBatch)
    if enterprise_id is not None:q=q.where(SimulationBatch.enterprise_id==enterprise_id)
    for x in db.scalars(q.order_by(SimulationBatch.id.desc()).limit(limit)).all():rows.append({"task_type":"BATCH","id":x.id,"status":x.status,"created_at":x.created_at,"finished_at":x.finished_at,"failure_reason":None})
    version_ids=select(ScenarioVersion.id).where(ScenarioVersion.scenario_id.in_(scenario_ids))
    for x in db.scalars(select(RiskAssessmentRun).where(RiskAssessmentRun.scenario_version_id.in_(version_ids)).order_by(RiskAssessmentRun.id.desc()).limit(limit)).all():rows.append({"task_type":"RISK","id":x.id,"status":"SUCCESS","created_at":x.created_at,"finished_at":x.created_at,"failure_reason":None,"scenario_version_id":x.scenario_version_id,"simulation_task_id":x.simulation_task_id})
    q=select(ReportTask)
    if enterprise_id is not None:q=q.where(ReportTask.enterprise_id==enterprise_id)
    for x in db.scalars(q.order_by(ReportTask.id.desc()).limit(limit)).all():rows.append({"task_type":"REPORT","id":x.id,"status":x.status,"created_at":x.created_at,"finished_at":x.generated_at,"failure_reason":x.failure_reason,"scenario_version_id":x.scenario_version_id,"simulation_task_id":x.simulation_task_id})
    return sorted(rows,key=lambda x:x["created_at"] or datetime.min,reverse=True)[:limit]
def trace(db:Session,scenario_version_id=None,data_source_id=None):
    nodes=[];edges=[]
    def add(kind,obj,label=None):
        if obj is None:return None
        key=f"{kind}:{obj.id}";nodes.append({"key":key,"type":kind,"id":obj.id,"label":label or f"{kind} #{obj.id}","status":getattr(obj,"status",None)});return key
    if scenario_version_id is not None:
        version=db.get(ScenarioVersion,scenario_version_id)
        if not version:raise LookupError("scenario version not found")
        scenario=db.get(Scenario,version.scenario_id);s=add("SCENARIO",scenario,getattr(scenario,"name",None));v=add("SCENARIO_VERSION",version,f"Version {version.version_number}");edges.append({"from":s,"to":v})
        for task in db.scalars(select(SimulationTask).where(SimulationTask.scenario_version_id==version.id)).all():
            t=add("SIMULATION_TASK",task);edges.append({"from":v,"to":t})
            for cost in db.scalars(select(CarbonCostAssessment).where(CarbonCostAssessment.task_id==task.id)).all():edges.append({"from":t,"to":add("CARBON_ASSESSMENT",cost)})
            for risk in db.scalars(select(RiskAssessmentRun).where(RiskAssessmentRun.simulation_task_id==task.id)).all():edges.append({"from":t,"to":add("RISK_ASSESSMENT",risk)})
            for report in db.scalars(select(ReportTask).where(ReportTask.simulation_task_id==task.id)).all():
                r=add("REPORT_TASK",report);edges.append({"from":t,"to":r})
                for file in db.scalars(select(ReportFile).where(ReportFile.report_task_id==report.id)).all():edges.append({"from":r,"to":add("REPORT_FILE",file,file.file_name)})
    if data_source_id is not None:
        source=db.get(DataSource,data_source_id)
        if not source:raise LookupError("data source not found")
        s=add("DATA_SOURCE",source,source.name)
        for device in db.scalars(select(Device).where(Device.data_source_id==source.id)).all():
            d=add("DEVICE",device,device.name);edges.append({"from":s,"to":d});metric_count=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.device_id==device.id)) or 0
            key=f"DEVICE_METRIC:{device.id}";nodes.append({"key":key,"type":"DEVICE_METRIC","id":device.id,"label":f"{metric_count} metrics","status":None});edges.append({"from":d,"to":key})
            carbon_count=db.scalar(select(func.count()).select_from(CarbonAccountingResult).where(CarbonAccountingResult.device_id==device.id)) or 0
            if carbon_count:key=f"CARBON_ACCOUNTING_RESULT:{device.id}";nodes.append({"key":key,"type":"CARBON_ACCOUNTING_RESULT","id":device.id,"label":f"{carbon_count} results","status":None});edges.append({"from":d,"to":key})
    return {"nodes":nodes,"edges":edges}
def overview(db:Session,enterprise_id=None):
    ds=data_sources(db,enterprise_id);ps=providers(db,enterprise_id);ts=tasks(db,enterprise_id,100);alerts=[]
    for x in ds:
        if x["status"] not in {"ACTIVE","OK","SUCCESS"}:alerts.append({"level":"HIGH","category":"DATA_SOURCE","message":f'{x["name"]} 状态为 {x["status"]}',"occurred_at":x["last_failure_at"]})
        if x["quality_rate"] is not None and x["quality_rate"]<.9:alerts.append({"level":"MEDIUM","category":"DATA_QUALITY","message":f'{x["name"]} 数据质量率低于 90%',"occurred_at":x["last_sync_at"]})
    for p in ps:
        if p["using_fallback"]:alerts.append({"level":"MEDIUM","category":"PROVIDER","message":f'{p["provider"]} 无动态数据，当前使用 fallback',"occurred_at":None})
    for t in ts:
        if t["status"] in {"FAILED","ERROR"}:alerts.append({"level":"HIGH","category":t["task_type"],"message":t["failure_reason"] or f'{t["task_type"]} #{t["id"]} failed',"occurred_at":t["finished_at"] or t["created_at"]})
    from app.services.acquisition_runtime_service import scheduler,mqtt_manager
    h=health(db);return {"health":h,"acquisition_services":{"rest_scheduler":scheduler.health(),"mqtt_manager":mqtt_manager.health()},"data_source_count":len(ds),"normal_data_source_count":sum(x["status"] in {"ACTIVE","OK","SUCCESS"} for x in ds),"abnormal_data_source_count":sum(x["status"] not in {"ACTIVE","OK","SUCCESS"} for x in ds),"providers":ps,"latest_system_exception_time":max((x["occurred_at"] for x in alerts if x["occurred_at"]),default=None),"alerts":alerts,"configuration":{"default_timezone":"Asia/Shanghai","default_emission_factor_mode":"DYNAMIC_WITH_ANNUAL_FALLBACK","default_electricity_price_mode":"DYNAMIC_WITH_FIXED_FALLBACK","file_storage_type":"LOCAL_FILESYSTEM","api_base_configuration":"ENVIRONMENT_OR_SAME_ORIGIN"},"models":["PV","WIND","STORAGE","HVAC","LIGHTING","EV_CHARGER","GREEN_POWER"]}
