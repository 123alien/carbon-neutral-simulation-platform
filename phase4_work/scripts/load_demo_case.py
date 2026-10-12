"""Idempotently load the P3-1 demo case through public APIs and import endpoints."""
from __future__ import annotations

import json
import os
import sys
import csv
from datetime import datetime
from pathlib import Path

if os.getenv("ALLOW_SYNTHETIC_VALIDATION") != "1":
    raise RuntimeError("synthetic validation loading is disabled; set ALLOW_SYNTHETIC_VALIDATION=1 only in an isolated test environment")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./validation_fixture.db")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select

from app.database import SessionLocal
from app.main import app
from app.models import DataSource, DataSourceRuntimeState, DeviceMetric, ElectricityPriceTimeseries, EmissionFactor, GridEmissionFactorTimeseries, LoadTimeseries, WeatherTimeseries

DATA = ROOT / "demo_data"
client = TestClient(app)


def ok(response, label: str):
    if response.status_code >= 300:
        raise RuntimeError(f"{label}: HTTP {response.status_code}: {response.text[:1000]}")
    return response.json()


def first_or_create(rows: list[dict], key: str, value, path: str, payload: dict) -> dict:
    found = next((x for x in rows if x.get(key) == value), None)
    return found or ok(client.post(path, json=payload), f"create {value}")


def upload(path: str, file_name: str, options: dict, confirm: bool) -> dict:
    with (DATA / file_name).open("rb") as stream:
        response = client.post(path, files={"file": (file_name, stream, "text/csv")}, data={"options": json.dumps(options, ensure_ascii=False)})
    body = ok(response, path)
    if not confirm and not body.get("can_confirm", False):
        raise RuntimeError(f"preview rejected {file_name}: {body.get('errors', [])[:3]}")
    return body


def main() -> None:
    site_spec = json.loads((DATA / "site.json").read_text(encoding="utf-8"))
    building_specs = json.loads((DATA / "buildings.json").read_text(encoding="utf-8"))
    equipment = json.loads((DATA / "devices.json").read_text(encoding="utf-8"))

    enterprises = ok(client.get("/api/enterprises"), "list enterprises")
    enterprise = first_or_create(enterprises, "name", "智慧低碳示范园区", "/api/enterprises", {"name":"智慧低碳示范园区","region":"DEMO_REGION","industry":"产业园区（示范仿真）","base_year":2024,"building_area":33800,"population":1580})
    enterprise_id = enterprise["id"]

    sites = ok(client.get("/api/sites", params={"enterprise_id":enterprise_id}), "list sites")
    site_payload = {k:v for k,v in site_spec.items() if k!="data_classification"}
    site_payload.update({"enterprise_id":enterprise_id,"organization_node_id":None,"status":"ACTIVE","metadata_json":{"classification":"DEMO_SIMULATION","demo":True,"notice":"示范仿真数据，非真实企业实测"},"longitude":114.31,"latitude":30.52,"geometry_json":None})
    site = first_or_create(sites,"code",site_spec["code"],"/api/sites",site_payload)
    site_id = site["id"]

    buildings = ok(client.get(f"/api/sites/{site_id}/buildings"), "list buildings")
    building_by_code = {x["code"]:x for x in buildings}
    for spec in building_specs:
        payload={**spec,"organization_node_id":None,"status":"ACTIVE","metadata_json":{"classification":"DEVELOPMENT/DEMO/VALIDATION"},"longitude":None,"latitude":None,"geometry_json":None}
        building_by_code[spec["code"]]=first_or_create(buildings,"code",spec["code"],f"/api/sites/{site_id}/buildings",payload)
        buildings=list(building_by_code.values())

    systems = ok(client.get("/api/energy-systems",params={"site_id":site_id}),"list systems")
    system_by_code={x["code"]:x for x in systems}
    for spec in equipment["energy_systems"]:
        payload={**spec,"site_id":site_id,"building_id":None,"status":"ACTIVE","metadata_json":{"classification":"DEVELOPMENT/DEMO/VALIDATION"}}
        system_by_code[spec["code"]]=first_or_create(systems,"code",spec["code"],"/api/energy-systems",payload);systems=list(system_by_code.values())

    source_specs=[
        ("园区总电表物联网接入","MQTT",{"purpose":"HOURLY_LOAD","timezone":"Asia/Shanghai","classification":"DEMO_SIMULATION","demo_runtime":True}),
        ("办公楼A电表物联网接入","MQTT",{"purpose":"BUILDING_LOAD","timezone":"Asia/Shanghai","classification":"DEMO_SIMULATION","demo_runtime":True}),
        ("光伏监控接口","REST_API",{"purpose":"PV","timezone":"Asia/Shanghai","classification":"DEMO_SIMULATION","demo_runtime":True}),
        ("风电监控接口","REST_API",{"purpose":"WIND","timezone":"Asia/Shanghai","classification":"DEMO_SIMULATION","demo_runtime":True}),
        ("储能管理第三方系统","THIRD_PARTY",{"purpose":"STORAGE","timezone":"Asia/Shanghai","classification":"DEMO_SIMULATION","demo_runtime":True}),
        ("充电桩运营平台","THIRD_PARTY",{"purpose":"EV","timezone":"Asia/Shanghai","classification":"DEMO_SIMULATION","demo_runtime":True}),
        ("空调楼控接口","REST_API",{"purpose":"HVAC","timezone":"Asia/Shanghai","classification":"DEMO_SIMULATION","demo_runtime":True}),
        ("照明系统仿真文件","FILE",{"purpose":"LIGHTING","timezone":"Asia/Shanghai","classification":"DEMO_SIMULATION","demo_runtime":True}),
    ]
    sources=ok(client.get("/api/data-sources",params={"enterprise_id":enterprise_id}),"list sources")
    source_by_name={x["name"]:x for x in sources}
    for name,kind,config in source_specs:
        source_by_name[name]=first_or_create(sources,"name",name,"/api/data-sources",{"enterprise_id":enterprise_id,"site_id":site_id,"data_nature":"SIMULATED" if kind=="FILE" else None,"name":name,"source_type":kind,"config_json":config,"credentials":None,"status":"ACTIVE"});sources=list(source_by_name.values())

    devices=ok(client.get("/api/devices",params={"enterprise_id":enterprise_id}),"list devices")
    device_by_code={x["external_id"]:x for x in devices}
    for spec in equipment["devices"]:
        building=building_by_code.get(spec.get("building"));system=system_by_code[spec["system"]]
        position={"coordinate_system":"LOCAL","x":spec["position"][0],"y":spec["position"][1],"z":spec["position"][2]}
        metadata={"classification":"DEVELOPMENT/DEMO/VALIDATION","site_id":site_id,"building_id":building["id"] if building else None,"energy_system_id":system["id"],**{k:v for k,v in spec.items() if k in {"capacity_kw"}}}
        source_name={"PV":"光伏监控接口","WIND":"风电监控接口","STORAGE":"储能管理第三方系统","EV_CHARGER":"充电桩运营平台","HVAC":"空调楼控接口","LIGHTING":"照明系统仿真文件"}.get(spec["type"],"园区总电表物联网接入")
        payload={"enterprise_id":enterprise_id,"data_source_id":source_by_name[source_name]["id"],"external_id":spec["code"],"name":spec["name"],"device_type":spec["type"],"metadata_json":metadata,"status":"ACTIVE","longitude":None,"latitude":None,"position_json":position,"geometry_json":None}
        device_by_code[spec["code"]]=first_or_create(devices,"external_id",spec["code"],"/api/devices",payload);devices=list(device_by_code.values())

    meters=ok(client.get("/api/metering-points",params={"site_id":site_id}),"list meters")
    meter_specs=[("MP-MAIN","园区总用电计量点","METER-MAIN","ES-ELEC","power_kw","ELECTRICITY","kW")]
    meter_specs += [(f"MP-{b['code']}",f"{b['name']}用电计量点",f"METER-{b['code']}","ES-ELEC","power_kw","ELECTRICITY","kW") for b in building_specs]
    meter_specs += [("MP-PV","光伏发电计量点","PV-INV-01","ES-PV","generation_kw","PV","kW"),("MP-WIND","风电发电计量点","WIND-AGG-01","ES-WIND","generation_kw","WIND","kW"),("MP-STORAGE","储能充放电计量点","BESS-01","ES-STORAGE","power_kw","STORAGE","kW"),("MP-EV","EV 充电计量点","EV-AGG-20","ES-EV","load_kw","ELECTRICITY","kW")]
    for code,name,device_code,system_code,metric,energy,unit in meter_specs:
        device=device_by_code[device_code];building_id=device["metadata_json"].get("building_id")
        payload={"site_id":site_id,"building_id":building_id,"energy_system_id":system_by_code[system_code]["id"],"device_id":device["id"],"data_source_id":device["data_source_id"],"code":code,"name":name,"metric_type":metric,"energy_type":energy,"unit":unit,"status":"ACTIVE","metadata_json":{"classification":"DEMO_SIMULATION"}}
        first_or_create(meters,"code",code,"/api/metering-points",payload);meters=ok(client.get("/api/metering-points",params={"site_id":site_id}),"refresh meters")

    weather_sites=ok(client.get("/api/weather/sites",params={"enterprise_id":enterprise_id}),"weather sites")
    weather_site=first_or_create(weather_sites,"name","示范园区开发气象站","/api/weather/sites",{"enterprise_id":enterprise_id,"name":"示范园区开发气象站","latitude":30.5,"longitude":114.3,"timezone":"Asia/Shanghai","source":"SYNTHETIC_DEVELOPMENT"})

    with SessionLocal() as db:
        load_count=db.scalar(select(func.count()).select_from(LoadTimeseries).where(LoadTimeseries.enterprise_id==enterprise_id)) or 0
        weather_count=db.scalar(select(func.count()).select_from(WeatherTimeseries).where(WeatherTimeseries.site_id==weather_site["id"])) or 0
        price_count=db.scalar(select(func.count()).select_from(ElectricityPriceTimeseries).where(ElectricityPriceTimeseries.enterprise_id==enterprise_id)) or 0
        factor_count=db.scalar(select(func.count()).select_from(GridEmissionFactorTimeseries).where(GridEmissionFactorTimeseries.region=="DEMO_REGION")) or 0
        has_electricity_factor=bool(db.scalar(select(func.count()).select_from(EmissionFactor).where(EmissionFactor.region=="DEMO_REGION",EmissionFactor.energy_type=="electricity")))
        has_gas_factor=bool(db.scalar(select(func.count()).select_from(EmissionFactor).where(EmissionFactor.region=="DEMO_REGION",EmissionFactor.energy_type=="natural_gas")))
        metric_count=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.device_id.in_([x["id"] for x in device_by_code.values()]))) or 0

    load_options={"enterprise_id":enterprise_id,"mapping":{"timestamp":"timestamp","load":"load_kw"},"load_unit":"kW","timezone":"Asia/Shanghai","interval_minutes":60,"source":"SYNTHETIC_DEVELOPMENT"}
    if load_count < 8784:
        load_preview=upload("/api/loads/hourly/import/preview","hourly_load_2024.csv",load_options,False)
        upload("/api/loads/hourly/import/confirm","hourly_load_2024.csv",load_options,True)
    else:
        load_preview={"valid_rows":load_count,"reused":True}
    weather_options={"site_id":weather_site["id"],"mapping":{"timestamp":"timestamp","temperature_c":"temperature_c","humidity_pct":"humidity_pct","ghi_w_m2":"ghi_w_m2","dni_w_m2":"dni_w_m2","dhi_w_m2":"dhi_w_m2","wind_speed_m_s":"wind_speed_m_s","cloud_cover_pct":"cloud_cover_pct"},"timezone":"Asia/Shanghai","interval_minutes":60,"source":"SYNTHETIC_DEVELOPMENT"}
    if weather_count < 8784:
        weather_preview=upload("/api/weather/import/preview","weather_2024.csv",weather_options,False)
        upload("/api/weather/import/confirm","weather_2024.csv",weather_options,True)
    else:
        weather_preview={"valid_rows":weather_count,"reused":True}
    price_options={"enterprise_id":enterprise_id,"mapping":{"timestamp":"timestamp","purchase_price":"purchase_price_per_kwh","feed_in_tariff":"feed_in_tariff_per_kwh"},"timezone":"Asia/Shanghai","source":"SYNTHETIC_DEVELOPMENT"}
    if price_count < 8784:
        price_preview=upload("/api/market/prices/import/preview","electricity_price_2024.csv",price_options,False)
        upload("/api/market/prices/import/confirm","electricity_price_2024.csv",price_options,True)
    else:
        price_preview={"valid_rows":price_count,"reused":True}
    factor_options={"region":"DEMO_REGION","version":"DEMO-2024-HOURLY","mapping":{"timestamp":"timestamp","factor":"factor_kg_per_kwh"},"timezone":"Asia/Shanghai","source":"SYNTHETIC_DEVELOPMENT"}
    if factor_count < 8784:
        factor_preview=upload("/api/market/grid-factors/import/preview","grid_emission_factor_2024.csv",factor_options,False)
        upload("/api/market/grid-factors/import/confirm","grid_emission_factor_2024.csv",factor_options,True)
    else:
        factor_preview={"valid_rows":factor_count,"reused":True}

    if not has_electricity_factor:
        ok(client.post("/api/emission-factors",json={"region":"DEMO_REGION","year":2024,"energy_type":"electricity","factor":0.56,"unit":"kgCO2/kWh","source":"SYNTHETIC_DEVELOPMENT","version":"DEMO-2024-FALLBACK"}),"electricity factor")
    if not has_gas_factor:
        ok(client.post("/api/emission-factors",json={"region":"DEMO_REGION","year":2024,"energy_type":"natural_gas","factor":2.162,"unit":"kgCO2/m3","source":"SYNTHETIC_DEVELOPMENT","version":"DEMO-2024-GAS"}),"gas factor")

    if metric_count < 100000:
        rows=csv.DictReader((DATA/"device_metrics_2024.csv").open(encoding="utf-8-sig")); batch=[]
        device_lookup={code:(item["id"],item["data_source_id"]) for code,item in device_by_code.items()}
        with SessionLocal() as db:
            for row in rows:
                device_id,data_source_id=device_lookup[row["device_external_id"]]
                value=float(row["value"])
                if not (-1_000_000 <= value <= 1_000_000): raise RuntimeError(f"L2 range rejected: {row}")
                batch.append({"device_id":device_id,"data_source_id":data_source_id,"timestamp":datetime.fromisoformat(row["timestamp"]),"metric_name":row["metric_name"],"value":value,"unit":row["unit"],"quality":"VALID","raw_json":{"classification":"DEMO_SIMULATION","validated":"L1/L2/L3_SEED"}})
                if len(batch)>=5000: db.execute(insert(DeviceMetric),batch);batch=[]
            if batch:db.execute(insert(DeviceMetric),batch)
            now=datetime(2024,12,31,23)
            for source in db.scalars(select(DataSource).where(DataSource.enterprise_id==enterprise_id)).all():
                source.last_sync_at=now
                count=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==source.id)) or 0
                state=db.scalar(select(DataSourceRuntimeState).where(DataSourceRuntimeState.data_source_id==source.id))
                if state is None:state=DataSourceRuntimeState(data_source_id=source.id);db.add(state)
                state.runtime_status="RUNNING";state.connected=True;state.subscribed=source.source_type=="MQTT";state.last_success_at=now;state.last_message_at=now;state.last_received_count=min(count,24);state.last_persisted_count=min(count,24);state.received_count=count;state.persisted_count=count;state.records_fetched=count
            db.commit()

    contracts=ok(client.get("/api/market/green-power/contracts",params={"enterprise_id":enterprise_id}),"contracts")
    if not any(x["name"]=="2024 开发验证绿电合同" for x in contracts):
        ok(client.post("/api/market/green-power/contracts",json={"enterprise_id":enterprise_id,"name":"2024 开发验证绿电合同","start_at":"2024-01-01T00:00:00+08:00","end_at":"2025-01-01T00:00:00+08:00","purchase_share":0.15,"emission_factor_kg_per_kwh":0,"premium_per_kwh":0.06,"status":"ACTIVE","source":"SYNTHETIC_DEVELOPMENT"}),"green contract")

    print(json.dumps({"enterprise_id":enterprise_id,"site_id":site_id,"weather_site_id":weather_site["id"],"buildings":len(building_by_code),"systems":len(system_by_code),"devices":len(device_by_code),"meters":len(meter_specs),"sources":len(source_by_name),"previews":{"load":load_preview["valid_rows"],"weather":weather_preview["valid_rows"],"price":price_preview["valid_rows"],"factor":factor_preview["valid_rows"]}},ensure_ascii=False))


if __name__ == "__main__":
    main()
