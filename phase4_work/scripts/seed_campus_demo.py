"""Build a deterministic campus case on the existing park-centred data model.

The dataset is explicitly DEMO_SIMULATION.  It contains no video, face,
identity, or cross-camera tracking result.  Spatial identifiers are stable
business keys stored in existing metadata JSON fields so this first trial does
not require a database migration.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from app.adapters import ExtractedRecord
from app.database import SessionLocal
from app.models import Building, DataSource, Device, DeviceMetric, EnergySystem, Enterprise, MeteringPoint, Site
from app.services import data_source_service

CAMPUS_ID = "CAMPUS-DEMO-001"
NOTICE = {
    "data_class": "DEMO_SIMULATION",
    "data_notice": "示范仿真数据",
    "rules_driven": True,
    "campus_id": CAMPUS_ID,
    "timezone": "Asia/Shanghai",
}

BUILDINGS = [
    ("TCH", "教学楼", "TEACHING", 16800, 6, 3200, 1.00),
    ("LAB", "实验楼", "LAB", 12800, 5, 1200, 1.18),
    ("ADM", "行政楼", "OFFICE", 8600, 6, 680, 0.72),
    ("LIB", "图书馆", "LIBRARY", 14200, 7, 2200, 0.92),
    ("DOR", "学生宿舍", "DORMITORY", 22600, 10, 2800, 1.12),
    ("DIN", "食堂及综合服务楼", "CANTEEN", 9800, 4, 1500, 0.82),
]


def one(db, model, **where):
    return db.scalar(select(model).filter_by(**where))


def ensure(db, model, where, values):
    obj = one(db, model, **where)
    if obj is None:
        obj = model(**values); db.add(obj); db.flush()
    return obj


def floor_areas(building_code: str, floors: int) -> list[dict]:
    result = []
    for floor in range(1, floors + 1):
        floor_id = f"{CAMPUS_ID}-{building_code}-F{floor:02d}"
        result.append({
            "floor_id": floor_id,
            "floor_number": floor,
            "areas": [
                {"area_id": f"{floor_id}-A01", "area_name": "主要使用区", "area_type": "PRIMARY_USE"},
                {"area_id": f"{floor_id}-A02", "area_name": "公共区域", "area_type": "COMMON"},
                {"area_id": f"{floor_id}-A03", "area_name": "机电及设备区", "area_type": "MEP"},
            ],
        })
    return result


def weather(local: datetime) -> tuple[float, float, float]:
    day = local.timetuple().tm_yday; hour = local.hour + local.minute / 60
    seasonal = 17 + 11 * math.sin(2 * math.pi * (day - 105) / 366)
    temperature = seasonal + 4.5 * math.sin(2 * math.pi * (hour - 8) / 24)
    daylight = max(0.0, math.sin(math.pi * (hour - 6) / 12))
    cloud = 0.78 + 0.12 * math.sin(day * 0.31) + 0.07 * math.sin(day * 0.073)
    irradiance = max(0.0, 920 * daylight * max(0.45, min(0.96, cloud)))
    wind = max(0.4, 4.8 + 1.8 * math.sin(day * 0.23) + 1.1 * math.sin(hour * 0.47))
    return temperature, irradiance, wind


def occupancy(building: str, local: datetime) -> float:
    h = local.hour + local.minute / 60; weekday = local.weekday() < 5
    if building == "TCH":
        if not weekday: return 0.10
        return 1.0 if any(a <= h < b for a,b in ((8,10),(10,12),(14,16),(16,18))) else 0.30 if 7 <= h < 21 else 0.05
    if building == "LAB": return (0.82 if weekday and 8 <= h < 21 else 0.18 if 8 <= h < 22 else 0.06)
    if building == "ADM": return (0.90 if weekday and 8 <= h < 18 else 0.08)
    if building == "LIB": return (0.78 if 8 <= h < 22 else 0.10) * (0.86 if not weekday else 1.0)
    if building == "DOR":
        return 0.92 if h >= 22 or h < 7 else 0.68 if 7 <= h < 9 or 18 <= h < 22 else 0.26
    if building == "DIN":
        meal = max(math.exp(-((h-7.2)/0.8)**2), math.exp(-((h-12.1)/1.0)**2), math.exp(-((h-18.0)/1.1)**2))
        return 0.12 + 0.88 * meal
    return 0.1


def building_values(code: str, scale: float, local: datetime) -> dict[str, tuple[float, str]]:
    occ = occupancy(code, local); temp, _, _ = weather(local); h = local.hour
    base = {"TCH":95,"LAB":150,"ADM":68,"LIB":105,"DOR":120,"DIN":82}[code] * scale
    process = 55 * scale if code == "LAB" and 8 <= h < 22 else 0
    kitchen = 70 * scale * occ if code == "DIN" else 0
    lighting = (8 + 72 * occ) * scale * (1.12 if h < 7 or h >= 18 else 0.82)
    cooling = max(0, temp - 24) * (14 + 34 * occ) * scale
    heating = max(0, 12 - temp) * (9 + 22 * occ) * scale
    hvac = cooling + heating
    electricity = base * (0.28 + 0.72 * occ) + process + kitchen + lighting + hvac
    # Water follows occupancy. Dormitory and canteen keep explicit morning/meal peaks.
    water = (0.16 + 2.5 * occ) * scale
    if code == "DOR": water *= 1.65 if 6 <= h < 9 or 20 <= h < 23 else 0.82
    if code == "DIN": water *= 2.4
    gas = (7 + 88 * occ) * scale if code == "DIN" else 0
    return {
        "energy_kwh": (electricity, "kWh"),
        "water_m3": (water, "m3"),
        "hvac_power_kw": (hvac, "kW"),
        "power_kw": (lighting, "kW"),
        "gas_m3": (gas, "m3"),
    }


def campus_values(local: datetime, previous_soc_kwh: float) -> tuple[dict[str, tuple[float,str]], float]:
    temp, irradiance, wind = weather(local); h = local.hour; weekday = local.weekday() < 5
    pv_power = 780 * irradiance / 1000 * 0.82
    wind_ratio = 0 if wind < 3 or wind >= 25 else 1 if wind >= 12 else ((wind - 3) / 9) ** 3
    wind_power = 180 * wind_ratio
    ev_factor = 0.82 if weekday and (7 <= h < 10 or 16 <= h < 20) else 0.28 if weekday and 10 <= h < 16 else 0.08
    ev_power = 24 * 7 * 0.62 * ev_factor
    capacity=960.0; min_soc=0.15*capacity; max_soc=0.90*capacity
    charge = 120.0 if 1 <= h < 6 else 0.0
    discharge = 150.0 if 17 <= h < 21 else 0.0
    charge = min(charge, max(0, (max_soc-previous_soc_kwh)/0.95))
    discharge = min(discharge, max(0, (previous_soc_kwh-min_soc)*0.95))
    soc = previous_soc_kwh + charge*0.95 - discharge/0.95
    return {
        "pv_power_kw": (pv_power,"kW"), "wind_power_kw": (wind_power,"kW"),
        "ev_power_kw": (ev_power,"kW"), "storage_charge_kw": (charge,"kW"),
        "storage_discharge_kw": (discharge,"kW"), "soc_pct": (soc/capacity*100,"%"),
        "temperature_c": (temp,"C"), "irradiance_w_m2": (irradiance,"W/m2"),
        "wind_speed_m_s": (wind,"m/s"),
    }, soc


def make_record(device, device_type, timestamp, metric, value, unit, building_id=None, floor_id=None, area_id=None):
    iso=timestamp.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
    return ExtractedRecord({
        "device_external_id":device,"device_name":device,"device_type":device_type,
        "timestamp":iso,"metric_name":metric,"value":round(value,5),"unit":unit,
        "source_record_id":f"{device}:{iso}:{metric}", **NOTICE,
        "building_id":building_id,"floor_id":floor_id,"area_id":area_id,
    })


def source(db, enterprise_id, site_id, name, code):
    config={"timezone":"UTC","field_mapping":{},"source_record_id_path":"source_record_id",**NOTICE,"source_code":code}
    obj=ensure(db,DataSource,{"enterprise_id":enterprise_id,"name":name},{"enterprise_id":enterprise_id,"site_id":site_id,"name":name,"source_type":"FILE","data_nature":"SIMULATED","config_json":config,"status":"ACTIVE","collection_mode":"MANUAL","schedule_enabled":False})
    obj.site_id=site_id;obj.config_json=config;obj.data_nature="SIMULATED";return obj


def main(hours: int):
    if os.getenv("DEMO_MODE") != "1": raise RuntimeError("set DEMO_MODE=1 before inserting demonstration data")
    with SessionLocal() as db:
        enterprise=ensure(db,Enterprise,{"name":"智慧低碳示范校园"},{"name":"智慧低碳示范校园","region":"湖北省武汉市（示范场景）","industry":"高等教育","base_year":2024,"building_area":84800,"population":11580})
        site=ensure(db,Site,{"enterprise_id":enterprise.id,"code":CAMPUS_ID},{"enterprise_id":enterprise.id,"code":CAMPUS_ID,"name":"智慧低碳示范校园","site_type":"CAMPUS","address":"校园综合能源与碳管理示范场景","area_m2":196000,"population":11580,"timezone":"Asia/Shanghai","status":"ACTIVE","metadata_json":{**NOTICE,"calendar":"2024校历规则","spatial_schema_version":"1.0"}})
        source_obj=source(db,enterprise.id,site.id,"校园综合能源示范数据", "CAMPUS-ENERGY-2024")
        system_specs=[("ELEC","校园供配电系统","ELECTRICITY"),("WATER","校园给水系统","WATER"),("GAS","食堂燃气系统","GAS"),("PV","屋顶分布式光伏系统","PV"),("WIND","小型风力发电示范系统","WIND"),("BESS","校园储能系统","STORAGE"),("EV","校园充电设施","EV_CHARGING"),("HVAC","建筑空调系统","HVAC"),("LIGHT","建筑照明系统","LIGHTING")]
        systems={code:ensure(db,EnergySystem,{"site_id":site.id,"code":f"{CAMPUS_ID}-SYS-{code}"},{"site_id":site.id,"code":f"{CAMPUS_ID}-SYS-{code}","name":name,"system_type":kind,"status":"ACTIVE","metadata_json":NOTICE}) for code,name,kind in system_specs}
        devices={}
        for index,(code,name,btype,area,floors,pop,scale) in enumerate(BUILDINGS,1):
            bid=f"{CAMPUS_ID}-BLD-{code}"
            building=ensure(db,Building,{"site_id":site.id,"code":bid},{"site_id":site.id,"code":bid,"name":name,"building_type":btype,"area_m2":area,"floor_count":floors,"population":pop,"status":"ACTIVE","metadata_json":{**NOTICE,"building_id":bid,"floors":floor_areas(f"BLD-{code}",floors)},"position_json":{"coordinate_system":"CAMPUS_LOCAL_METERS","x":(index-1)%3*90-90,"y":0,"z":((index-1)//3)*90-45}})
            for suffix,dtype,syskey,label in [("ELEC","ELECTRIC_METER","ELEC","用电"),("WATER","WATER_METER","WATER","用水"),("HVAC","HVAC","HVAC","空调"),("LIGHT","LIGHTING","LIGHT","照明")]+([("GAS","GAS_METER","GAS","天然气")] if code=="DIN" else []):
                ext=f"{bid}-DEV-{suffix}"; dev=ensure(db,Device,{"enterprise_id":enterprise.id,"external_id":ext},{"enterprise_id":enterprise.id,"data_source_id":source_obj.id,"external_id":ext,"name":f"{name}{label}设备","device_type":dtype,"metadata_json":{**NOTICE,"building_id":bid,"floor_id":f"{bid}-F01","area_id":f"{bid}-F01-A03"},"status":"ACTIVE"});devices[(code,suffix)]=(dev,building)
                metric={"ELEC":("energy_kwh","ELECTRICITY","kWh"),"WATER":("water_m3","WATER","m3"),"HVAC":("hvac_power_kw","ELECTRICITY","kW"),"LIGHT":("power_kw","ELECTRICITY","kW"),"GAS":("gas_m3","GAS","m3")}[suffix]
                ensure(db,MeteringPoint,{"site_id":site.id,"code":f"{bid}-MP-{suffix}"},{"site_id":site.id,"building_id":building.id,"energy_system_id":systems[syskey].id,"device_id":dev.id,"data_source_id":source_obj.id,"code":f"{bid}-MP-{suffix}","name":f"{name}{label}计量点","metric_type":metric[0],"energy_type":metric[1],"unit":metric[2],"status":"ACTIVE","metadata_json":dev.metadata_json})
        campus_device_specs=[("PV","PV","PV","光伏阵列"),("WIND","WIND","WIND","风力发电机"),("EV","EV_CHARGER","EV","充电桩群"),("BESS","STORAGE","BESS","储能电站")]
        for suffix,dtype,syskey,label in campus_device_specs:
            ext=f"{CAMPUS_ID}-DEV-{suffix}";dev=ensure(db,Device,{"enterprise_id":enterprise.id,"external_id":ext},{"enterprise_id":enterprise.id,"data_source_id":source_obj.id,"external_id":ext,"name":label,"device_type":dtype,"metadata_json":{**NOTICE,"building_id":None,"floor_id":None,"area_id":f"{CAMPUS_ID}-OUTDOOR-{suffix}"},"status":"ACTIVE"});devices[("CAMPUS",suffix)]=(dev,None)
            metric={"PV":("active_power_kw","ELECTRICITY","kW"),"WIND":("active_power_kw","ELECTRICITY","kW"),"EV":("power_kw","ELECTRICITY","kW"),"BESS":("soc_pct","ELECTRICITY","%")} [suffix]
            ensure(db,MeteringPoint,{"site_id":site.id,"code":f"{CAMPUS_ID}-MP-{suffix}"},{"site_id":site.id,"building_id":None,"energy_system_id":systems[syskey].id,"device_id":dev.id,"data_source_id":source_obj.id,"code":f"{CAMPUS_ID}-MP-{suffix}","name":f"{label}主计量点","metric_type":metric[0],"energy_type":metric[1],"unit":metric[2],"status":"ACTIVE","metadata_json":dev.metadata_json})
        db.commit()
        existing=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==source_obj.id)) or 0
        pv_device=devices[("CAMPUS","PV")][0]
        current_hours=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.device_id==pv_device.id,DeviceMetric.metric_name=="active_power_kw")) or 0
        if current_hours>=hours:
            print(f"校园拓扑已存在，数据源已有 {existing} 条事实、{current_hours} 小时，无需重复生成")
            return
        last_soc=db.scalar(select(DeviceMetric.value).where(DeviceMetric.device_id==devices[("CAMPUS","BESS")][0].id,DeviceMetric.metric_name=="soc_pct").order_by(DeviceMetric.timestamp.desc()).limit(1))
        start=datetime(2024,1,1,tzinfo=timezone(timedelta(hours=8)));soc=(last_soc/100*960) if last_soc is not None else 0.50*960;batch=[]
        for step in range(current_hours,hours):
            local=start+timedelta(hours=step)
            for code,_,_,_,_,_,scale in BUILDINGS:
                vals=building_values(code,scale,local)
                for suffix,metric in (("ELEC","energy_kwh"),("WATER","water_m3"),("HVAC","hvac_power_kw"),("LIGHT","power_kw")) + (("GAS","gas_m3"),) if code=="DIN" else (("ELEC","energy_kwh"),("WATER","water_m3"),("HVAC","hvac_power_kw"),("LIGHT","power_kw")):
                    dev,bld=devices[(code,suffix)];value,unit=vals[metric]
                    batch.append(make_record(dev.external_id,dev.device_type,local,metric,value,unit,bld.code,f"{bld.code}-F01",f"{bld.code}-F01-A03"))
            cv,soc=campus_values(local,soc)
            mapping={"PV":[("pv_power_kw","active_power_kw")],"WIND":[("wind_power_kw","active_power_kw")],"EV":[("ev_power_kw","power_kw")],"BESS":[("soc_pct","soc_pct"),("storage_charge_kw","storage_charge_kw"),("storage_discharge_kw","storage_discharge_kw")]}
            for suffix,metrics in mapping.items():
                dev,_=devices[("CAMPUS",suffix)]
                for source_metric,target_metric in metrics:
                    value,unit=cv[source_metric];batch.append(make_record(dev.external_id,dev.device_type,local,target_metric,value,unit,area_id=f"{CAMPUS_ID}-OUTDOOR-{suffix}"))
            if len(batch)>=1000:
                data_source_service.ingest_records(db,source_obj,batch);batch=[]
        if batch:data_source_service.ingest_records(db,source_obj,batch)
        total=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==source_obj.id)) or 0
        print(f"校园示范数据已生成：campus_id={CAMPUS_ID}, hours={hours}, facts={total}, data_class=DEMO_SIMULATION")


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--hours",type=int,default=24*30);args=parser.parse_args()
    if args.hours<48:raise SystemExit("--hours must be at least 48 to cover weekday/weekend patterns")
    main(args.hours)
