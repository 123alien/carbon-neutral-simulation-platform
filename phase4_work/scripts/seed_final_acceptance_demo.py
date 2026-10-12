"""Idempotently add final acceptance demo cases to the configured development DB."""
from __future__ import annotations

import os
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if os.getenv("DEMO_MODE") != "1":
    raise RuntimeError("set DEMO_MODE=1 before inserting demonstration data")

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from sqlalchemy import func, select

from app.adapters import ExtractedRecord
from app.database import SessionLocal
from app.models import (Building, CarbonAccountingRun, DataSource, Device, DeviceMetric,
                        EmissionFactor, EnergySystem, Enterprise, MeteringPoint,
                        OrganizationNode, Site)
from app.schemas.accounting import CarbonAccountingRunRequest
from app.services import carbon_accounting_service, data_source_service
from app.services.acceptance_demo_service import telemetry

NOTICE={"classification":"DEMO_SIMULATION","data_notice":"示范仿真数据","rules_driven":True}

def one(db,model,**where):return db.scalar(select(model).filter_by(**where))
def ensure(db,model,where,values):
    obj=one(db,model,**where)
    if obj is None:obj=model(**values);db.add(obj);db.flush()
    return obj

def source(db,eid,sid,name,kind,automatic=True):
    config={"url":f"http://127.0.0.1:8000/api/acceptance-demo/telemetry/{kind}","allow_insecure":True,"verify_tls":False,"trust_env":False,"data_path":"records","source_record_id_path":"source_record_id","timezone":"UTC","pagination_mode":"NONE","incremental_mode":"NONE","field_mapping":{},**NOTICE}
    obj=ensure(db,DataSource,{"enterprise_id":eid,"name":name},{"enterprise_id":eid,"site_id":sid,"name":name,"source_type":"REST_API","config_json":config,"status":"ACTIVE","collection_mode":"INTERVAL" if automatic else "MANUAL","schedule_enabled":automatic,"interval_minutes":15 if automatic else None})
    obj.site_id=sid;obj.source_type="REST_API";obj.config_json=config;obj.collection_mode="INTERVAL" if automatic else "MANUAL";obj.schedule_enabled=automatic;obj.interval_minutes=15 if automatic else None;obj.status="ACTIVE"
    return obj

def bind_existing_automatic_sources(db,enterprise,site):
    specs=[("WIND","风力发电自动采集（示范仿真数据）","WIND-AGG-01"),("EV","充电桩自动采集（示范仿真数据）","EV-AGG-20"),("STORAGE","储能自动采集（示范仿真数据）","BESS-01"),("HVAC","空调自动采集（示范仿真数据）","HVAC-B01"),("LIGHTING","照明自动采集（示范仿真数据）","LIGHT-AGG"),("EMS","第三方能源管理系统接口（示范仿真数据）","METER-MAIN")]
    now=datetime.now(timezone.utc).replace(second=0,microsecond=0)
    for kind,name,code in specs:
        src=source(db,enterprise.id,site.id,name,kind);device=one(db,Device,enterprise_id=enterprise.id,external_id=code)
        if device:device.data_source_id=src.id
        db.flush()
        existing=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==src.id)) or 0
        if not existing:
            for step in range(96):
                payload=telemetry(kind,now-timedelta(minutes=15*(95-step)))
                data_source_service.ingest_records(db,src,[ExtractedRecord(row) for row in payload["records"]])
    water_system=ensure(db,EnergySystem,{"site_id":site.id,"code":"ES-WATER"},{"site_id":site.id,"building_id":None,"code":"ES-WATER","name":"园区用水系统","system_type":"WATER","status":"ACTIVE","metadata_json":NOTICE})
    water_src=source(db,enterprise.id,site.id,"园区用水自动采集（示范仿真数据）","WATER")
    water_device=ensure(db,Device,{"enterprise_id":enterprise.id,"external_id":"WATER-MAIN-01"},{"enterprise_id":enterprise.id,"data_source_id":water_src.id,"external_id":"WATER-MAIN-01","name":"园区总水表","device_type":"WATER_METER","metadata_json":{**NOTICE,"site_id":site.id,"energy_system_id":water_system.id},"status":"ACTIVE"})
    water_device.data_source_id=water_src.id
    ensure(db,MeteringPoint,{"site_id":site.id,"code":"MP-WATER-MAIN"},{"site_id":site.id,"building_id":None,"energy_system_id":water_system.id,"device_id":water_device.id,"data_source_id":water_src.id,"code":"MP-WATER-MAIN","name":"园区总用水计量点","metric_type":"water_m3","energy_type":"WATER","unit":"m3","status":"ACTIVE","metadata_json":NOTICE})
    existing=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==water_src.id)) or 0
    if not existing:
        for step in range(24*7):
            payload=telemetry("WATER",now-timedelta(hours=24*7-1-step))
            data_source_service.ingest_records(db,water_src,[ExtractedRecord(row) for row in payload["records"]])

def regional_cases(db):
    enterprise=ensure(db,Enterprise,{"name":"示范区域公共建筑群"},{"name":"示范区域公共建筑群","region":"DEMO_REGION","industry":"区域公共建筑（示范仿真）","base_year":2024,"building_area":76000,"population":9200})
    region=ensure(db,OrganizationNode,{"enterprise_id":enterprise.id,"code":"REGION-DEMO"},{"enterprise_id":enterprise.id,"parent_id":None,"name":"示范区域","level":"REGION","code":"REGION-DEMO","metadata_json":NOTICE})
    cases=[("REGION-PARK","低碳产业园","PARK","产业园综合楼",36000,2600,1.0),("REGION-CAMPUS","绿色校园","CAMPUS","教学综合楼",28000,5200,.72),("REGION-PUBLIC","公共机构示范点","PUBLIC_INSTITUTION","公共服务中心",12000,1400,.43)]
    activities=[]
    for code,name,site_type,building_name,area,pop,scale in cases:
        org=ensure(db,OrganizationNode,{"enterprise_id":enterprise.id,"code":code},{"enterprise_id":enterprise.id,"parent_id":region.id,"name":name,"level":"BUILDING_PARK","code":code,"metadata_json":NOTICE})
        site=ensure(db,Site,{"enterprise_id":enterprise.id,"code":code},{"enterprise_id":enterprise.id,"organization_node_id":org.id,"code":code,"name":name,"site_type":site_type,"address":"示范区域仿真案例","area_m2":area,"population":pop,"timezone":"Asia/Shanghai","status":"ACTIVE","metadata_json":NOTICE})
        site.organization_node_id=org.id
        building=ensure(db,Building,{"site_id":site.id,"code":f"{code}-B01"},{"site_id":site.id,"organization_node_id":org.id,"code":f"{code}-B01","name":building_name,"building_type":"OFFICE" if site_type!="CAMPUS" else "TEACHING","area_m2":area,"floor_count":8,"population":pop,"status":"ACTIVE","metadata_json":NOTICE})
        for energy,system_type,metric,device_type,unit in [("ELECTRICITY","ELECTRICITY","energy_kwh","ELECTRIC_METER","kWh"),("WATER","WATER","water_m3","WATER_METER","m3")]:
            system=ensure(db,EnergySystem,{"site_id":site.id,"code":f"{code}-{energy}"},{"site_id":site.id,"building_id":building.id,"code":f"{code}-{energy}","name":f"{name}{'用电' if energy=='ELECTRICITY' else '用水'}系统","system_type":system_type,"status":"ACTIVE","metadata_json":NOTICE})
            src=source(db,enterprise.id,site.id,f"{name}{'电力' if energy=='ELECTRICITY' else '用水'}接口（示范仿真数据）","EMS" if energy=="ELECTRICITY" else "WATER",automatic=False)
            dev=ensure(db,Device,{"enterprise_id":enterprise.id,"external_id":f"{code}-{energy}-METER"},{"enterprise_id":enterprise.id,"data_source_id":src.id,"external_id":f"{code}-{energy}-METER","name":f"{name}{'电表' if energy=='ELECTRICITY' else '水表'}","device_type":device_type,"metadata_json":{**NOTICE,"site_id":site.id,"building_id":building.id,"organization_node_id":org.id},"status":"ACTIVE"})
            ensure(db,MeteringPoint,{"site_id":site.id,"code":f"MP-{code}-{energy}"},{"site_id":site.id,"building_id":building.id,"energy_system_id":system.id,"device_id":dev.id,"data_source_id":src.id,"code":f"MP-{code}-{energy}","name":f"{name}{'用电' if energy=='ELECTRICITY' else '用水'}计量点","metric_type":metric,"energy_type":energy,"unit":unit,"status":"ACTIVE","metadata_json":NOTICE})
            existing=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==src.id)) or 0
            if not existing:
                start=datetime(2024,1,1,tzinfo=timezone.utc)
                records=[]
                for hour in range(24*7):
                    ts=start+timedelta(hours=hour);local_hour=(ts.hour+8)%24;workday=ts.weekday()<5
                    if energy=="ELECTRICITY":value=(135 if workday and 8<=local_hour<19 else 54)*scale;unit_value="kWh"
                    else:value=(2.8 if workday and 8<=local_hour<19 else .65)*scale*(1.55 if 11<=local_hour<14 else 1);unit_value="m3"
                    iso=ts.isoformat().replace("+00:00","Z")
                    records.append(ExtractedRecord({"device_external_id":dev.external_id,"device_name":dev.name,"device_type":device_type,"timestamp":iso,"metric_name":metric,"value":round(value,4),"unit":unit_value,"source_record_id":f"{dev.external_id}:{iso}:{metric}","data_class":"DEMO_SIMULATION","data_notice":"示范仿真数据"}))
                data_source_service.ingest_records(db,src,records)
        for month in range(1,13):
            activities += [{"timestamp":f"2024-{month:02d}-01T00:00:00Z","energy_type":"electricity","value":180000*scale*(1+.14*abs(month-7)/6),"unit":"kWh","organization_node_id":org.id,"source":"示范区域月度用电"},{"timestamp":f"2024-{month:02d}-01T00:00:00Z","energy_type":"natural_gas","value":3600*scale*(1.5 if month in {1,2,12} else .65),"unit":"m3","organization_node_id":org.id,"source":"示范区域月度燃气"},{"timestamp":f"2024-{month:02d}-01T00:00:00Z","energy_type":"heat","value":24000*scale*(1.7 if month in {1,2,12} else .3),"unit":"kWh","organization_node_id":org.id,"source":"示范区域月度外购热力"}]
    factors=[("electricity",.56,"kgCO2/kWh"),("natural_gas",2.162,"kgCO2/m3"),("coal",2.42,"kgCO2/kg"),("oil",3.10,"kgCO2/kg"),("heat",.11,"kgCO2/kWh")]
    for energy,factor,unit in factors:
        ensure(db,EmissionFactor,{"region":"DEMO_REGION","year":2024,"energy_type":energy},{"region":"DEMO_REGION","year":2024,"energy_type":energy,"factor":factor,"unit":unit,"source":"示范仿真核算参数","version":"GBT32150-DEMO-V1"})
    if not one(db,CarbonAccountingRun,enterprise_id=enterprise.id,name="GB/T 32150 区域示范核算"):
        req=CarbonAccountingRunRequest(enterprise_id=enterprise.id,name="GB/T 32150 区域示范核算",period_start="2024-01-01T00:00:00Z",period_end="2025-01-01T00:00:00Z",scopes=["SCOPE_1","SCOPE_2"],standard_basis="GB/T 32150-2015 按规范要求实现核算逻辑验证（不代表认证）",activities=activities)
        carbon_accounting_service.run(db,req)

def main():
    with SessionLocal() as db:
        demo=one(db,Enterprise,name="智慧低碳示范园区")
        if demo:
            site=one(db,Site,enterprise_id=demo.id,code="DEMO-PARK-001")
            if site:bind_existing_automatic_sources(db,demo,site)
        regional_cases(db);db.commit()
    print("最终验收示范数据已加载：自动采集、用水、校园、公共机构、区域核算（数据性质：示范仿真数据）")

if __name__=="__main__":
    main()
