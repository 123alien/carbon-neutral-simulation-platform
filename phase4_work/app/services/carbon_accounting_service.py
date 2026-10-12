from collections import defaultdict
from datetime import datetime,timezone
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.accounting import CarbonAccountingRegistry
from app.models import CarbonAccountingRun,CarbonAccountingResult,Device,DeviceMetric,Enterprise,OrganizationNode
from app.providers import DatabaseGridEmissionFactorProvider
from app.services.energy_service import resolve_emission_factor

LEVELS={"ENTERPRISE","BUILDING_PARK","REGION"};SCOPES={"SCOPE_1","SCOPE_2"}
METRIC_ACTIVITY={"energy_kwh":("electricity","kWh"),"electricity_kwh":("electricity","kWh"),"gas_m3":("natural_gas","m3"),"natural_gas_m3":("natural_gas","m3"),"coal_kg":("coal","kg"),"oil_kg":("oil","kg"),"heat_kwh":("heat","kWh")}

def _utc(value):return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
def create_organization(db,data):
    if data.level.upper() not in LEVELS:raise ValueError(f"level must be one of {sorted(LEVELS)}")
    if db.get(Enterprise,data.enterprise_id) is None:raise LookupError("enterprise not found")
    if data.parent_id:
        parent=db.get(OrganizationNode,data.parent_id)
        if parent is None or parent.enterprise_id!=data.enterprise_id:raise ValueError("invalid parent organization")
    obj=OrganizationNode(**data.model_dump(exclude={"level"}),level=data.level.upper());db.add(obj);db.commit();db.refresh(obj);return obj
def list_organizations(db,enterprise_id):return list(db.scalars(select(OrganizationNode).where(OrganizationNode.enterprise_id==enterprise_id).order_by(OrganizationNode.id)).all())

def _device_activities(db,enterprise_id,start,end):
    rows=db.execute(select(DeviceMetric,Device).join(Device,Device.id==DeviceMetric.device_id).where(Device.enterprise_id==enterprise_id,DeviceMetric.timestamp>=start,DeviceMetric.timestamp<end,DeviceMetric.metric_name.in_(METRIC_ACTIVITY))).all()
    return [{"timestamp":metric.timestamp,"energy_type":METRIC_ACTIVITY[metric.metric_name][0],"value":metric.value,"unit":METRIC_ACTIVITY[metric.metric_name][1],"organization_node_id":(device.metadata_json or {}).get("organization_node_id"),"device_id":device.id,"scope":None,"source":f"device_metric:{metric.id}"} for metric,device in rows]

def run(db:Session,req):
    enterprise=db.get(Enterprise,req.enterprise_id)
    if enterprise is None:raise LookupError("enterprise not found")
    start,end=_utc(req.period_start),_utc(req.period_end)
    if end<=start:raise ValueError("period_end must be later than period_start")
    scopes={scope.upper() for scope in req.scopes}
    if not scopes or not scopes<=SCOPES:raise ValueError("scopes must contain SCOPE_1 and/or SCOPE_2")
    activities=[{**item.model_dump(),"timestamp":_utc(item.timestamp)} for item in req.activities]
    if req.include_device_metrics:activities.extend(_device_activities(db,req.enterprise_id,start,end))
    activities=[item for item in activities if start<=item["timestamp"]<end]
    dynamic=DatabaseGridEmissionFactorProvider(db).get_hourly_details(enterprise.region or "",start,end)
    model=CarbonAccountingRegistry.get("ENERGY")
    run_obj=CarbonAccountingRun(enterprise_id=req.enterprise_id,name=req.name,period_start=start,period_end=end,status="RUNNING",scopes_json=sorted(scopes),summary_json={});db.add(run_obj);db.flush()
    total=0;counts=defaultdict(int)
    try:
        for item in activities:
            org_id=item.get("organization_node_id");device_id=item.get("device_id")
            if org_id:
                org=db.get(OrganizationNode,org_id)
                if org is None or org.enterprise_id!=req.enterprise_id:raise ValueError("organization does not belong to enterprise")
            if device_id:
                device=db.get(Device,device_id)
                if device is None or device.enterprise_id!=req.enterprise_id:raise ValueError("device does not belong to enterprise")
            energy=item["energy_type"].lower();detail=dynamic.get(item["timestamp"]) if energy=="electricity" else None
            if detail is None:
                factor=resolve_emission_factor(db,enterprise.region,item["timestamp"].year,energy)
                if factor is None:raise ValueError(f"emission factor not found for {energy} at {item['timestamp']}")
                detail={"factor":float(factor.factor),"unit":factor.unit,"source":factor.source,"version":factor.version}
            calculation=model.calculate(energy,item["value"],item["unit"],detail["factor"],detail["unit"],item.get("scope"))
            if calculation.scope not in scopes:continue
            result=CarbonAccountingResult(run_id=run_obj.id,enterprise_id=req.enterprise_id,organization_node_id=org_id,device_id=device_id,timestamp=item["timestamp"],energy_type=energy,scope=calculation.scope,activity_value=calculation.canonical_value,activity_unit=calculation.canonical_unit,original_activity_value=float(item["value"]),original_activity_unit=item["unit"],emission_factor=detail["factor"],factor_unit=detail["unit"],factor_source=detail.get("source"),factor_version=detail.get("version") or "UNVERSIONED",formula=calculation.formula,standard_basis=req.standard_basis,emission_t=calculation.emission_t,activity_source=item.get("source"));db.add(result);total+=calculation.emission_t;counts[calculation.scope]+=1
        run_obj.status="SUCCESS";run_obj.summary_json={"activity_count":sum(counts.values()),"total_emission_t":total,"scope_counts":dict(counts),"dynamic_factor_points_available":len(dynamic)};db.commit();db.refresh(run_obj);return run_obj
    except Exception:
        db.rollback();raise

def get_run(db,run_id):
    obj=db.get(CarbonAccountingRun,run_id)
    if obj is None:raise LookupError("accounting run not found")
    return obj
def list_runs(db,enterprise_id=None,start_time=None,end_time=None,status=None):
    stmt=select(CarbonAccountingRun)
    if enterprise_id is not None:stmt=stmt.where(CarbonAccountingRun.enterprise_id==enterprise_id)
    if start_time is not None:stmt=stmt.where(CarbonAccountingRun.period_end>_utc(start_time))
    if end_time is not None:stmt=stmt.where(CarbonAccountingRun.period_start<_utc(end_time))
    if status is not None:stmt=stmt.where(CarbonAccountingRun.status==status)
    return list(db.scalars(stmt.order_by(CarbonAccountingRun.created_at.desc(),CarbonAccountingRun.id.desc())).all())
def results(db,run_id,energy_type=None,scope=None,device_id=None,organization_node_id=None,start_time=None,end_time=None):
    get_run(db,run_id);stmt=select(CarbonAccountingResult).where(CarbonAccountingResult.run_id==run_id)
    for column,value in [(CarbonAccountingResult.energy_type,energy_type),(CarbonAccountingResult.scope,scope),(CarbonAccountingResult.device_id,device_id),(CarbonAccountingResult.organization_node_id,organization_node_id)]:
        if value is not None:stmt=stmt.where(column==value)
    if start_time is not None:stmt=stmt.where(CarbonAccountingResult.timestamp>=_utc(start_time))
    if end_time is not None:stmt=stmt.where(CarbonAccountingResult.timestamp<_utc(end_time))
    return list(db.scalars(stmt.order_by(CarbonAccountingResult.timestamp,CarbonAccountingResult.id)).all())
def statistics(db,run_id,granularity,dimension,timezone_name,energy_type=None,scope=None,organization_node_id=None,start_time=None,end_time=None):
    if granularity not in {"day","month","year"}:raise ValueError("granularity must be day, month or year")
    if dimension not in {"energy","device","organization","organization_level","scope"}:raise ValueError("dimension must be energy, device, organization, organization_level or scope")
    try:zone=ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:raise ValueError(f"unknown timezone: {timezone_name}") from exc
    rows=results(db,run_id,energy_type,scope,None,organization_node_id,start_time,end_time);grouped=defaultdict(lambda:[0.0,0]);org_levels={obj.id:obj.level for obj in db.scalars(select(OrganizationNode)).all()}
    for row in rows:
        local=row.timestamp.replace(tzinfo=timezone.utc).astimezone(zone)
        bucket=local.replace(hour=0,minute=0,second=0,microsecond=0)
        if granularity=="month":bucket=bucket.replace(day=1)
        elif granularity=="year":bucket=bucket.replace(month=1,day=1)
        key={"energy":row.energy_type,"device":str(row.device_id or "UNASSIGNED"),"organization":str(row.organization_node_id or "ENTERPRISE"),"organization_level":org_levels.get(row.organization_node_id,"ENTERPRISE"),"scope":row.scope}[dimension]
        grouped[(bucket,key)][0]+=row.emission_t;grouped[(bucket,key)][1]+=1
    items=[{"bucket_start":bucket,"dimension_key":key,"emission_t":values[0],"record_count":values[1]} for (bucket,key),values in sorted(grouped.items(),key=lambda x:(x[0][0],x[0][1]))]
    return {"run_id":run_id,"granularity":granularity,"dimension":dimension,"timezone":timezone_name,"total_emission_t":sum(row.emission_t for row in rows),"items":items}
