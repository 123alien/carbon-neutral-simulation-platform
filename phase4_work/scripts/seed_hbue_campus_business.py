"""Bind rule-driven demonstration business data to verified HBUE OSM buildings."""
from __future__ import annotations
import argparse,json,math,os,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from sqlalchemy import func,select
from app.adapters import ExtractedRecord
from app.database import SessionLocal
from app.models import Building,DataSource,Device,DeviceMetric,EnergySystem,Enterprise,MeteringPoint,Site
from app.services import data_source_service

CAMPUS_ID="HBUE";NOTICE={"data_class":"DEMO_SIMULATION","data_notice":"示范仿真数据","campus_id":CAMPUS_ID,"rules_driven":True,"spatial_source":"OpenStreetMap / ODbL"}
# id, profile, floors, population, intensity scale; floors/population/capacity are simulation assumptions.
CORE=[("HBUE-B001","ADMIN",6,650,.72),("HBUE-B002","ACTIVITY",4,1200,.76),("HBUE-B003","SPORTS",3,900,.88),("HBUE-B004","HOSPITAL",5,300,.82),("HBUE-B006","OFFICE",9,1500,1.05),("HBUE-B009","CANTEEN",3,1800,.90),("HBUE-B041","LAB",5,1200,1.12),("HBUE-B043","LAB",5,1200,1.08),("HBUE-B042","TEACHING",6,2600,.95),("HBUE-B046","ART",6,1300,.90),("HBUE-B048","TEACHING",6,2400,.92),("HBUE-B049","TEACHING",6,2800,1.00),("HBUE-B119","TEACHING",6,2600,.96),("HBUE-B120","TEACHING",6,2600,.96),("HBUE-B124","DORMITORY",12,3200,1.18),("HBUE-B125","OFFICE",23,2200,1.25)]
FACTOR_ELECTRICITY=.5703;FACTOR_GAS=2.162
def one(db,model,**where):return db.scalar(select(model).filter_by(**where))
def ensure(db,model,where,values):
    obj=one(db,model,**where)
    if obj is None:obj=model(**values);db.add(obj);db.flush()
    return obj
def geo_features():return {x["properties"]["building_id"]:x for x in json.loads((ROOT/"spatial_data/hbue/hbue_buildings.geojson").read_text(encoding="utf-8"))["features"]}
def center(feature):
    pts=feature["geometry"]["coordinates"][0][:-1];return sum(p[0] for p in pts)/len(pts),sum(p[1] for p in pts)/len(pts)
def floor_schema(bid,floors):return [{"floor_id":f"{bid}-F{i:02d}","areas":[{"area_id":f"{bid}-F{i:02d}-A01","area_name":"主要使用区"},{"area_id":f"{bid}-F{i:02d}-A02","area_name":"公共区域"},{"area_id":f"{bid}-F{i:02d}-A03","area_name":"设备区域"}]} for i in range(1,floors+1)]
def weather(t):
    day=t.timetuple().tm_yday;h=t.hour;temp=17+11*math.sin(2*math.pi*(day-105)/366)+4.5*math.sin(2*math.pi*(h-8)/24);solar=max(0,920*math.sin(math.pi*(h-6)/12)) if 6<=h<=18 else 0;return temp,solar
def occupancy(profile,t):
    h=t.hour;weekday=t.weekday()<5
    if profile=="TEACHING":return 1 if weekday and h in {8,9,10,11,14,15,16,17} else .25 if weekday and 7<=h<21 else .06
    if profile=="LAB":return .86 if weekday and 8<=h<21 else .18 if 8<=h<22 else .05
    if profile in {"ADMIN","OFFICE"}:return .9 if weekday and 8<=h<18 else .08
    if profile=="DORMITORY":return .92 if h>=22 or h<7 else .68 if h in {7,8,18,19,20,21} else .25
    if profile=="CANTEEN":return .15+.85*max(math.exp(-((h-7)/.9)**2),math.exp(-((h-12)/1.1)**2),math.exp(-((h-18)/1.2)**2))
    if profile=="SPORTS":return .72 if 16<=h<22 else .38 if 8<=h<16 else .05
    if profile=="HOSPITAL":return .55 if 8<=h<18 else .22
    if profile=="ACTIVITY":return .72 if 9<=h<21 else .08
    if profile=="ART":return .78 if weekday and 8<=h<21 else .16
    return .1
def values(profile,scale,t):
    occ=occupancy(profile,t);temp,_=weather(t);base={"TEACHING":72,"LAB":125,"ADMIN":56,"OFFICE":92,"DORMITORY":108,"CANTEEN":76,"SPORTS":65,"HOSPITAL":74,"ACTIVITY":61,"ART":88}[profile]*scale
    lighting=(7+52*occ)*scale*(1.12 if t.hour<7 or t.hour>=18 else .82);hvac=(max(0,temp-24)*(10+28*occ)+max(0,12-temp)*(8+20*occ))*scale;process=(48*scale if profile=="LAB" and 8<=t.hour<22 else 0);electricity=base*(.28+.72*occ)+lighting+hvac+process;water=(.12+2.3*occ)*scale
    if profile=="DORMITORY":water*=1.7 if t.hour in {6,7,8,20,21,22} else .82
    if profile=="CANTEEN":water*=2.5
    gas=(6+92*occ)*scale if profile=="CANTEEN" else 0
    return {"energy_kwh":(electricity,"kWh"),"water_m3":(water,"m3"),"hvac_power_kw":(hvac,"kW"),"lighting_power_kw":(lighting,"kW"),"gas_m3":(gas,"m3")}
def record(device,t,metric,value,unit,bid):
    iso=t.astimezone(timezone.utc).isoformat().replace("+00:00","Z");return ExtractedRecord({"device_external_id":device.external_id,"device_name":device.name,"device_type":device.device_type,"timestamp":iso,"metric_name":metric,"value":round(value,5),"unit":unit,"source_record_id":f"{device.external_id}:{iso}:{metric}",**NOTICE,"building_id":bid,"floor_id":f"{bid}-F01","area_id":f"{bid}-F01-A03"})
def main(hours):
    if os.getenv("DEMO_MODE")!="1":raise RuntimeError("set DEMO_MODE=1 before inserting demonstration data")
    features=geo_features()
    missing=[bid for bid,*_ in CORE if bid not in features]
    if missing:raise RuntimeError(f"verified spatial features missing: {missing}")
    with SessionLocal() as db:
        enterprise=ensure(db,Enterprise,{"name":"湖北经济学院智慧低碳校园"},{"name":"湖北经济学院智慧低碳校园","region":"湖北省武汉市江夏区","industry":"高等教育（示范仿真场景）","base_year":2024,"building_area":None,"population":None})
        site=ensure(db,Site,{"enterprise_id":enterprise.id,"code":CAMPUS_ID},{"enterprise_id":enterprise.id,"code":CAMPUS_ID,"name":"湖北经济学院智慧低碳校园","site_type":"CAMPUS","address":"武汉市江夏区藏龙岛开发区杨桥湖大道8号","timezone":"Asia/Shanghai","status":"ACTIVE","latitude":30.42023,"longitude":114.42966,"geometry_json":json.loads((ROOT/"spatial_data/hbue/hbue_campus_boundary.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"],"metadata_json":{**NOTICE,"spatial_crs":"EPSG:4326","business_binding_version":"1.0"}})
        ds=ensure(db,DataSource,{"enterprise_id":enterprise.id,"name":"湖北经济学院校园能碳示范数据"},{"enterprise_id":enterprise.id,"site_id":site.id,"name":"湖北经济学院校园能碳示范数据","source_type":"FILE","data_nature":"SIMULATED","config_json":{**NOTICE,"timezone":"UTC","field_mapping":{},"source_record_id_path":"source_record_id"},"status":"ACTIVE","collection_mode":"MANUAL","schedule_enabled":False})
        systems={code:ensure(db,EnergySystem,{"site_id":site.id,"code":f"HBUE-SYS-{code}"},{"site_id":site.id,"code":f"HBUE-SYS-{code}","name":name,"system_type":kind,"status":"ACTIVE","metadata_json":NOTICE}) for code,name,kind in [("ELEC","校园供配电系统","ELECTRICITY"),("WATER","校园给水系统","WATER"),("GAS","餐饮天然气系统","GAS"),("HVAC","建筑空调系统","HVAC"),("LIGHT","建筑照明系统","LIGHTING"),("PV","屋顶分布式光伏系统","PV"),("BESS","校园储能系统","STORAGE"),("EV","校园充电设施","EV_CHARGING")]}
        devices={};start=datetime(2024,1,1,tzinfo=timezone(timedelta(hours=8)))
        for bid,profile,floors,pop,scale in CORE:
            feature=features[bid];lon,lat=center(feature);name=feature["properties"]["name"];annual_e=annual_w=annual_g=0
            for step in range(8760):
                vals=values(profile,scale,start+timedelta(hours=step));annual_e+=vals["energy_kwh"][0];annual_w+=vals["water_m3"][0];annual_g+=vals["gas_m3"][0]
            annual_carbon=(annual_e*FACTOR_ELECTRICITY+annual_g*FACTOR_GAS)/1000
            meta={**NOTICE,"building_id":bid,"osm_id":feature["properties"]["osm_id"],"business_type":profile,"parameter_source":"DEMO_SIMULATION_ASSUMPTION","floors":floor_schema(bid,floors),"annual_energy_kwh":round(annual_e,3),"annual_water_m3":round(annual_w,3),"annual_gas_m3":round(annual_g,3),"annual_emission_tco2e":round(annual_carbon,6),"electricity_factor_kgco2e_kwh":FACTOR_ELECTRICITY,"gas_factor_kgco2e_m3":FACTOR_GAS}
            b=ensure(db,Building,{"site_id":site.id,"code":bid},{"site_id":site.id,"code":bid,"name":name,"building_type":profile,"floor_count":floors,"population":pop,"status":"ACTIVE","longitude":lon,"latitude":lat,"geometry_json":feature["geometry"],"metadata_json":meta});b.metadata_json=meta;b.longitude=lon;b.latitude=lat;b.geometry_json=feature["geometry"]
            specs=[("ELEC","ELECTRIC_METER","ELEC","用电","energy_kwh","ELECTRICITY","kWh"),("WATER","WATER_METER","WATER","用水","water_m3","WATER","m3"),("HVAC","HVAC","HVAC","空调","hvac_power_kw","ELECTRICITY","kW"),("LIGHT","LIGHTING","LIGHT","照明","lighting_power_kw","ELECTRICITY","kW")]+([("GAS","GAS_METER","GAS","天然气","gas_m3","GAS","m3")] if profile=="CANTEEN" else [])
            for suffix,dtype,syscode,label,metric,energy,unit in specs:
                ext=f"{bid}-DEV-{suffix}";dev=ensure(db,Device,{"enterprise_id":enterprise.id,"external_id":ext},{"enterprise_id":enterprise.id,"data_source_id":ds.id,"external_id":ext,"name":f"{name}{label}设备","device_type":dtype,"status":"ACTIVE","longitude":lon,"latitude":lat,"metadata_json":{**NOTICE,"building_id":bid,"floor_id":f"{bid}-F01","area_id":f"{bid}-F01-A03"}});devices[(bid,suffix)]=dev
                ensure(db,MeteringPoint,{"site_id":site.id,"code":f"{bid}-MP-{suffix}"},{"site_id":site.id,"building_id":b.id,"energy_system_id":systems[syscode].id,"device_id":dev.id,"data_source_id":ds.id,"code":f"{bid}-MP-{suffix}","name":f"{name}{label}计量点","metric_type":metric,"energy_type":energy,"unit":unit,"status":"ACTIVE","metadata_json":dev.metadata_json})
        # Distributed assets are bound only to verified buildings, not floating campus anchors.
        for bid,suffix,dtype,syscode,label in [("HBUE-B125","PV","PV","PV","香帅楼屋顶光伏"),("HBUE-B002","BESS","STORAGE","BESS","活动中心储能站"),("HBUE-B003","EV","EV_CHARGER","EV","体育馆停车区充电桩")]:
            b=one(db,Building,site_id=site.id,code=bid);ext=f"{bid}-DEV-{suffix}";dev=ensure(db,Device,{"enterprise_id":enterprise.id,"external_id":ext},{"enterprise_id":enterprise.id,"data_source_id":ds.id,"external_id":ext,"name":label,"device_type":dtype,"status":"ACTIVE","longitude":b.longitude,"latitude":b.latitude,"metadata_json":{**NOTICE,"building_id":bid,"floor_id":None,"area_id":f"{bid}-OUTDOOR-{suffix}"}});devices[(bid,suffix)]=dev
            ensure(db,MeteringPoint,{"site_id":site.id,"code":f"{bid}-MP-{suffix}"},{"site_id":site.id,"building_id":b.id,"energy_system_id":systems[syscode].id,"device_id":dev.id,"data_source_id":ds.id,"code":f"{bid}-MP-{suffix}","name":f"{label}计量点","metric_type":"active_power_kw" if suffix=="PV" else "soc_pct" if suffix=="BESS" else "power_kw","energy_type":"ELECTRICITY","unit":"kW" if suffix!="BESS" else "%","status":"ACTIVE","metadata_json":dev.metadata_json})
        db.commit();existing=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==ds.id)) or 0
        if existing:print(f"HBUE业务拓扑已存在，已有 {existing} 条示范事实");return
        batch=[]
        for step in range(hours):
            t=start+timedelta(hours=step)
            for bid,profile,_,_,scale in CORE:
                vals=values(profile,scale,t)
                for suffix,metric in [("ELEC","energy_kwh"),("WATER","water_m3"),("HVAC","hvac_power_kw"),("LIGHT","lighting_power_kw")]+([("GAS","gas_m3")] if profile=="CANTEEN" else []):
                    value,unit=vals[metric];batch.append(record(devices[(bid,suffix)],t,metric,value,unit,bid))
            _,solar=weather(t);pv=720*solar/1000*.82;ev=(120 if t.weekday()<5 and t.hour in {7,8,17,18} else 25);soc=55+25*math.sin(2*math.pi*(t.hour-5)/24)
            for bid,suffix,metric,value,unit in [("HBUE-B125","PV","active_power_kw",pv,"kW"),("HBUE-B002","BESS","soc_pct",soc,"%"),("HBUE-B003","EV","power_kw",ev,"kW")]:batch.append(record(devices[(bid,suffix)],t,metric,value,unit,bid))
            if len(batch)>=1200:data_source_service.ingest_records(db,ds,batch);batch=[]
        if batch:data_source_service.ingest_records(db,ds,batch)
        total=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==ds.id));print(f"HBUE核心建筑绑定完成：buildings={len(CORE)}, hours={hours}, facts={total}, data_class=DEMO_SIMULATION")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--hours",type=int,default=24*30);a=p.parse_args();main(a.hours)
