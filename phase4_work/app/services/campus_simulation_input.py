"""Shared campus source for annual simulation and path recommendation."""
from datetime import datetime
from dataclasses import asdict
import hashlib,json
from sqlalchemy import select
from app.models import Site,Building,MeteringPoint,Device
from app.simulation.hourly import HourlyInput
from app.services.campus_live_demo_service import _year,PROFILES,TZ,values,weather,FACTOR_ELECTRICITY,FACTOR_GAS

def resolve_site(db,enterprise_id,site_id=None):
    sites=db.scalars(select(Site).where(Site.enterprise_id==enterprise_id)).all()
    if site_id is not None:
        site=next((s for s in sites if s.id==site_id),None)
        if site is None:raise ValueError('当前园区不属于所选单位')
        return site
    if len(sites)>1:raise ValueError('该单位包含多个园区，请明确选择园区，禁止混用负荷')
    return sites[0] if sites else None

def build(db,site,year):
    if not 2024<=year<=2060:raise ValueError('校园示范仿真年份须在2024至2060年之间')
    bs=db.scalars(select(Building).where(Building.site_id==site.id)).all()
    codes=tuple(sorted(b.code for b in bs if b.code in PROFILES and (b.metadata_json or {}).get('data_class')=='DEMO_SIMULATION'))
    if not codes:raise ValueError('当前园区尚未绑定校园示范建筑')
    ids=db.scalars(select(MeteringPoint.device_id).where(MeteringPoint.site_id==site.id)).all()
    kinds=set(db.scalars(select(Device.device_type).where(Device.id.in_(ids))).all())
    source=_year(year,codes,'PV' in kinds,'STORAGE' in kinds,'EV_CHARGER' in kinds)
    points=[]
    for row in source:
        t=datetime.fromisoformat(row['timestamp']);temp,solar=weather(t)
        gas=sum(values(*PROFILES[code],t)['gas_m3'][0] for code in codes)
        points.append(HourlyInput(timestamp=t,load_kwh=row['load_after_saving_kwh'],irradiation_wm2=solar,temperature_c=temp,
            existing_pv_kwh=row['pv_generation_kwh'],existing_ev_kwh=row['ev_charging_load_kwh'],direct_emission_t=gas*FACTOR_GAS/1000,
            grid_emission_factor_kg_per_kwh=FACTOR_ELECTRICITY))
    config={'storage':dict(capacity_kwh=840,max_charge_kw=120,max_discharge_kw=120,soc_initial=.5,soc_min=.1,soc_max=.9,
        charge_efficiency=.95,discharge_efficiency=.95,strategy='PEAK_VALLEY_ARBITRAGE',off_peak_hours=list(range(6)),peak_hours=[17,18,19,20])} if 'STORAGE' in kinds else {}
    provenance=dict(site_id=site.id,campus_id='HBUE',building_ids=list(codes),data_notice='示范仿真数据',
        source='HBUE-LIVE-1',year=year,hours=len(points),existing_assets=sorted(kinds),measure_semantics='新增或改造，不替换既有光伏、充电桩和储能',
        price_source='FUNCTION_PARAMETER_ONLY',parameter_sources='校园既有示范假设，非学校实测',baseline_config=config)
    return points,config,provenance

def combine(base,changes):
    result={**base,**changes}
    if 'storage' in base and 'storage' in changes:
        result['storage']={**base['storage'],**changes['storage']}
        for key in ('capacity_kwh','max_charge_kw','max_discharge_kw'):
            result['storage'][key]=float(base['storage'][key])+float(changes['storage'].get(key,0))
    return result

def freeze(points,config,provenance,price=.57,tariff=.42):
    from app.simulation.hourly import HourlySimulationEngine
    _,summary=HourlySimulationEngine(.5703,price,tariff).run(points,config)
    rows=[]
    for p in points:
        row=asdict(p);row['timestamp']=p.timestamp.isoformat();rows.append(row)
    payload={'schema_version':1,'provenance':provenance,'inputs':rows,'existing_config':config,
        'metrics':summary.__dict__,'scope1_t':sum(p.direct_emission_t for p in points),'factor':.5703,
        'prices':{'purchase':price,'feed_in':tariff,'source':'FUNCTION_PARAMETER_ONLY'},'model_version':'HBUE-LIVE-1 / HourlySimulationEngine'}
    payload['checksum']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return payload

def restore(frozen):
    payload={k:v for k,v in frozen.items() if k!='checksum'}
    checksum=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if checksum!=frozen.get('checksum'):raise ValueError('园区基准快照校验失败，禁止继续推演')
    return [HourlyInput(**{**row,'timestamp':datetime.fromisoformat(row['timestamp'])}) for row in frozen['inputs']]
