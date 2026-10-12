from collections import defaultdict
from datetime import datetime,timezone
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.models import Site,Building,EnergySystem,MeteringPoint,Enterprise,OrganizationNode,Device,DataSource,DeviceMetric,DataValidationLog,CarbonAccountingRun,CarbonAccountingResult

def _zone(name):
    try:return ZoneInfo(name)
    except ZoneInfoNotFoundError as e:raise ValueError(f"unknown timezone: {name}") from e
def _utc(v,z):return v.replace(tzinfo=z).astimezone(timezone.utc).replace(tzinfo=None) if v and v.tzinfo is None else (v.astimezone(timezone.utc).replace(tzinfo=None) if v else None)
def _bucket(v,g,z):
    x=v.replace(tzinfo=timezone.utc).astimezone(z)
    if g=="hour":return x.replace(minute=0,second=0,microsecond=0)
    if g=="day":return x.replace(hour=0,minute=0,second=0,microsecond=0)
    if g=="month":return x.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    return x.replace(month=1,day=1,hour=0,minute=0,second=0,microsecond=0)
def _check_granularity(g,carbon=False):
    allowed={"day","month","year"} if carbon else {"hour","day","month","year"}
    if g not in allowed:raise ValueError(f"granularity must be one of {sorted(allowed)}")
def _aggregate_metric(metric_name,values):
    """Extensive quantities accumulate; instantaneous SCADA signals average."""
    name=(metric_name or "").lower()
    return sum(values) if name.endswith(("_kwh","_m3","_kg","_t")) or name in {"energy","generation","consumption"} else sum(values)/len(values)
def _site(db,id):
    o=db.get(Site,id)
    if not o:raise LookupError("site not found")
    return o
def _building(db,id):
    o=db.get(Building,id)
    if not o:raise LookupError("building not found")
    return o
def create_site(db,data):
    if db.get(Enterprise,data.enterprise_id) is None:raise LookupError("enterprise not found")
    if data.organization_node_id:
        org=db.get(OrganizationNode,data.organization_node_id)
        if not org or org.enterprise_id!=data.enterprise_id:raise ValueError("organization node does not belong to enterprise")
    _zone(data.timezone);o=Site(**data.model_dump());db.add(o);db.commit();db.refresh(o);return o
def _is_validation_site(site):
    return (site.metadata_json or {}).get("data_class") in {"REAL_PUBLIC","REAL_PUBLIC_OFFICIAL"} or (site.metadata_json or {}).get("business_class") == "MODEL_VALIDATION"
def list_sites(db,enterprise_id=None,site_type=None,scope="ALL"):
    q=select(Site)
    if enterprise_id:q=q.where(Site.enterprise_id==enterprise_id)
    if site_type:q=q.where(Site.site_type==site_type.upper())
    rows=list(db.scalars(q.order_by(Site.id)).all())
    scope=scope.upper()
    if scope=="BUSINESS":return [x for x in rows if not _is_validation_site(x)]
    if scope=="VALIDATION":return [x for x in rows if _is_validation_site(x)]
    if scope!="ALL":raise ValueError("scope must be ALL, BUSINESS or VALIDATION")
    return rows
def get_site(db,id):return _site(db,id)
def create_building(db,site_id,data):
    site=_site(db,site_id)
    if data.organization_node_id:
        org=db.get(OrganizationNode,data.organization_node_id)
        if not org or org.enterprise_id!=site.enterprise_id:raise ValueError("organization node does not belong to site enterprise")
    o=Building(site_id=site_id,**data.model_dump());db.add(o);db.commit();db.refresh(o);return o
def list_buildings(db,site_id):_site(db,site_id);return list(db.scalars(select(Building).where(Building.site_id==site_id).order_by(Building.id)).all())
def get_building(db,id):return _building(db,id)
def create_system(db,data):
    _site(db,data.site_id)
    if data.building_id and _building(db,data.building_id).site_id!=data.site_id:raise ValueError("building does not belong to site")
    o=EnergySystem(**data.model_dump());db.add(o);db.commit();db.refresh(o);return o
def systems(db,site_id=None,building_id=None,system_type=None):
    q=select(EnergySystem)
    for col,val in [(EnergySystem.site_id,site_id),(EnergySystem.building_id,building_id),(EnergySystem.system_type,system_type.upper() if system_type else None)]:
        if val is not None:q=q.where(col==val)
    return list(db.scalars(q.order_by(EnergySystem.id)).all())
def get_system(db,id):
    o=db.get(EnergySystem,id)
    if not o:raise LookupError("energy system not found")
    return o
def create_meter(db,data):
    site=_site(db,data.site_id)
    if data.building_id and _building(db,data.building_id).site_id!=site.id:raise ValueError("building does not belong to site")
    if data.energy_system_id and get_system(db,data.energy_system_id).site_id!=site.id:raise ValueError("energy system does not belong to site")
    if data.device_id and (not (d:=db.get(Device,data.device_id)) or d.enterprise_id!=site.enterprise_id):raise ValueError("device does not belong to site enterprise")
    if data.data_source_id and (not (s:=db.get(DataSource,data.data_source_id)) or s.enterprise_id!=site.enterprise_id):raise ValueError("data source does not belong to site enterprise")
    o=MeteringPoint(**data.model_dump());db.add(o);db.commit();db.refresh(o);return o
def meters(db,**filters):
    q=select(MeteringPoint)
    for name,val in filters.items():
        if val is not None:q=q.where(getattr(MeteringPoint,name)==val)
    return list(db.scalars(q.order_by(MeteringPoint.id)).all())
def get_meter(db,id):
    o=db.get(MeteringPoint,id)
    if not o:raise LookupError("metering point not found")
    return o
def _metric_rows(db,mps,start,end,metric_name=None):
    ids={m.device_id for m in mps if m.device_id};names={m.metric_type for m in mps}
    if metric_name:names={metric_name}
    if not ids:return []
    q=select(DeviceMetric,DataSource).join(DataSource,DataSource.id==DeviceMetric.data_source_id).where(DeviceMetric.device_id.in_(ids),DeviceMetric.metric_name.in_(names))
    if start:q=q.where(DeviceMetric.timestamp>=start)
    if end:q=q.where(DeviceMetric.timestamp<end)
    return list(db.execute(q.order_by(DeviceMetric.timestamp)).all())
def timeseries(db,mp_id,start,end,timezone_name,granularity):
    mp=get_meter(db,mp_id);z=_zone(timezone_name);_check_granularity(granularity);rows=_metric_rows(db,[mp],_utc(start,z),_utc(end,z))
    grouped=defaultdict(list)
    for metric,source in rows:grouped[_bucket(metric.timestamp,granularity,z)].append(metric)
    data=[{"timestamp":ts,"value":_aggregate_metric(mp.metric_type,[x.value for x in vals]),"quality":"VALID" if all(x.quality=="VALID" for x in vals) else "WARNING"} for ts,vals in sorted(grouped.items())]
    return {"object_id":str(mp.id),"object_type":"METERING_POINT","metric":mp.metric_type,"energy_type":mp.energy_type,"unit":mp.unit,"start_time":start,"end_time":end,"timezone":timezone_name,"data_status":"OK" if data else "NO_DATA","data":data}
def devices_for(db,mps):
    ids=sorted({m.device_id for m in mps if m.device_id});return list(db.scalars(select(Device).where(Device.id.in_(ids)).order_by(Device.id)).all()) if ids else []
def device_overview(db,id):
    d=db.get(Device,id)
    if not d:raise LookupError("device not found")
    latest=db.scalar(select(DeviceMetric).where(DeviceMetric.device_id==id).order_by(DeviceMetric.timestamp.desc()))
    count=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.device_id==id)) or 0
    return {"device":d,"metric_count":count,"latest_timestamp":latest.timestamp if latest else None,"latest_quality":latest.quality if latest else None,"data_status":"OK" if latest else "NO_DATA"}
def device_telemetry(db,id,start,end,metric_name,timezone_name,granularity):
    d=db.get(Device,id)
    if not d:raise LookupError("device not found")
    z=_zone(timezone_name);_check_granularity(granularity);mps=list(db.scalars(select(MeteringPoint).where(MeteringPoint.device_id==id)).all());rows=_metric_rows(db,mps or [type("M",(),{"device_id":id,"metric_type":metric_name})()],_utc(start,z),_utc(end,z),metric_name)
    grouped=defaultdict(list)
    for metric,source in rows:grouped[(_bucket(metric.timestamp,granularity,z),metric.unit,source.name)].append(metric)
    data=[{"timestamp":key[0],"value":_aggregate_metric(metric_name,[x.value for x in vals]),"unit":key[1],"quality_status":"VALID" if all(x.quality=="VALID" for x in vals) else "WARNING","data_source":key[2]} for key,vals in sorted(grouped.items())]
    return {"object_id":str(id),"object_type":"DEVICE","metric":metric_name,"timezone":timezone_name,"data_status":"OK" if data else "NO_DATA","data":data}
def energy(db,building_id,start,end,granularity,energy_type,timezone_name):
    b=_building(db,building_id);mps=meters(db,building_id=b.id,energy_type=energy_type.upper() if energy_type else None);z=_zone(timezone_name);_check_granularity(granularity);rows=_metric_rows(db,mps,_utc(start,z),_utc(end,z));lookup={(m.device_id,m.metric_type):m for m in mps};grouped=defaultdict(list)
    for metric,source in rows:
        mp=lookup.get((metric.device_id,metric.metric_name));grouped[(_bucket(metric.timestamp,granularity,z),mp.energy_type,metric.unit)].append(metric)
    items=[{"timestamp":k[0],"energy_type":k[1],"unit":k[2],"value":sum(x.value for x in vals),"quality":"VALID" if all(x.quality=="VALID" for x in vals) else "WARNING"} for k,vals in sorted(grouped.items())]
    return {"building_id":b.id,"timezone":timezone_name,"data_status":"OK" if items else "NO_DATA","items":items}
def carbon(db,site_id=None,building_id=None,start=None,end=None,granularity="month",energy_type=None,scope=None,device_id=None):
    _check_granularity(granularity,True);site=_site(db,site_id) if site_id else _site(db,_building(db,building_id).site_id)
    latest_run=db.scalar(select(CarbonAccountingRun).where(CarbonAccountingRun.enterprise_id==site.enterprise_id,CarbonAccountingRun.status=="SUCCESS").order_by(CarbonAccountingRun.created_at.desc(),CarbonAccountingRun.id.desc()))
    if latest_run is None:return {"data_status":"NO_DATA","total_emission_t":None,"scope":{},"energy":{},"trend":[]}
    q=select(CarbonAccountingResult).where(CarbonAccountingResult.enterprise_id==site.enterprise_id,CarbonAccountingResult.run_id==latest_run.id)
    if building_id:
        b=_building(db,building_id)
        if b.site_id!=site.id:raise ValueError("building does not belong to site")
        ids=[d.id for d in devices_for(db,meters(db,building_id=b.id))];conditions=[]
        if b.organization_node_id:conditions.append(CarbonAccountingResult.organization_node_id==b.organization_node_id)
        if ids:conditions.append(CarbonAccountingResult.device_id.in_(ids))
        if not conditions:return {"data_status":"NO_DATA","total_emission_t":None,"scope":{},"energy":{},"trend":[]}
        from sqlalchemy import or_;q=q.where(or_(*conditions))
    elif site_id:
        ids=[d.id for d in devices_for(db,meters(db,site_id=site.id))];conditions=[]
        if site.organization_node_id:
            org_ids={site.organization_node_id};changed=True
            while changed:
                children=set(db.scalars(select(OrganizationNode.id).where(OrganizationNode.parent_id.in_(org_ids))).all())-org_ids
                changed=bool(children);org_ids.update(children)
            conditions.append(CarbonAccountingResult.organization_node_id.in_(org_ids))
        if ids:conditions.append(CarbonAccountingResult.device_id.in_(ids))
        if conditions:
            from sqlalchemy import or_;q=q.where(or_(*conditions))
    for col,val in [(CarbonAccountingResult.energy_type,energy_type),(CarbonAccountingResult.scope,scope),(CarbonAccountingResult.device_id,device_id)]:
        if val is not None:q=q.where(col==val)
    if start:q=q.where(CarbonAccountingResult.timestamp>=start)
    if end:q=q.where(CarbonAccountingResult.timestamp<end)
    rows=list(db.scalars(q.order_by(CarbonAccountingResult.timestamp)).all());group=defaultdict(float)
    for r in rows:group[_bucket(r.timestamp,granularity,timezone.utc)]+=r.emission_t
    return {"data_status":"OK" if rows else "NO_DATA","total_emission_t":sum(r.emission_t for r in rows) if rows else None,"scope":{s:sum(r.emission_t for r in rows if r.scope==s) for s in {r.scope for r in rows}},"energy":{e:sum(r.emission_t for r in rows if r.energy_type==e) for e in {r.energy_type for r in rows}},"factor_sources":sorted({r.factor_source for r in rows if r.factor_source}),"trend":[{"timestamp":k,"emission_t":v} for k,v in sorted(group.items())]}
def overview(db,site_id,building_id=None):
    site=_site(db,site_id);mps=meters(db,site_id=site.id,building_id=building_id) if building_id else meters(db,site_id=site.id);devs=devices_for(db,mps);source_ids={m.data_source_id for m in mps if m.data_source_id};rows=_metric_rows(db,mps,None,None);metrics=[r[0] for r in rows];latest=max((m.timestamp for m in metrics),default=None);valid=sum(m.quality=="VALID" for m in metrics);carbon_data=carbon(db,site_id=site.id,building_id=building_id)
    base={"device_count":len(devs),"data_source_count":len(source_ids),"metering_point_count":len(mps),"latest_energy":{"timestamp":latest,"values":[{"metric":m.metric_name,"value":m.value,"unit":m.unit,"quality":m.quality} for m in metrics if m.timestamp==latest]} if latest else None,"latest_carbon_emission_t":carbon_data["total_emission_t"],"data_completeness_rate":valid/len(metrics) if metrics else None,"anomaly_count":sum(m.quality!="VALID" for m in metrics),"latest_data_time":latest,"data_status":"OK" if metrics else "NO_DATA"}
    if building_id:base.update({"building":_building(db,building_id),"energy_system_count":len(systems(db,building_id=building_id))})
    else:base.update({"site":site,"building_count":len(list_buildings(db,site.id)),"energy_system_count":len(systems(db,site_id=site.id))})
    return base
