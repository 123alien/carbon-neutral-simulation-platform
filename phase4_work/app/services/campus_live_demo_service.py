"""Current-time campus demonstration, never an observed measurement.

Reuse the seeded campus occupancy and weather rules. No historical facts are
rewritten. Future measured feeds must be explicitly mapped before substitution.
"""
from datetime import datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo
import math
from sqlalchemy import select
from app.models import Building, Device, Site
from scripts.seed_hbue_campus_business import CORE, values, weather, FACTOR_ELECTRICITY, FACTOR_GAS

TZ=ZoneInfo('Asia/Shanghai')
PROFILES={row[0]:(row[1],row[4]) for row in CORE}

@lru_cache(maxsize=8)
def _year(year, codes, pv_enabled, storage_enabled, ev_enabled):
    start=datetime(year,1,1,tzinfo=TZ)
    hours=int((datetime(year+1,1,1,tzinfo=TZ)-start).total_seconds()/3600)
    points=[];soc=420.
    for step in range(hours):
        t=start+timedelta(hours=step)
        rows={code:values(*PROFILES[code],t) for code in codes}
        load=sum(r['energy_kwh'][0] for r in rows.values())
        gas=sum(r['gas_m3'][0] for r in rows.values())
        _,solar=weather(t)
        pv=720*solar/1000*.82 if pv_enabled else 0.
        ev=(120 if t.weekday()<5 and t.hour in (7,8,17,18) else 25) if ev_enabled else 0.
        demand=load+ev;charge=discharge=0.;before=soc
        if storage_enabled:
            if t.hour<6:charge=min(120.,(756-soc)/.95);soc+=charge*.95
            elif t.hour in (17,18,19,20):discharge=min(120.,max(0,demand-pv),(soc-84)*.95);soc-=discharge/.95
        else:soc=0.
        grid=max(0,demand+charge-pv-discharge);curtail=max(0,pv+discharge-demand-charge)
        emission=(grid*FACTOR_ELECTRICITY+gas*FACTOR_GAS)/1000
        p=dict(timestamp=t.isoformat(),load_after_saving_kwh=load,ev_charging_load_kwh=ev,
            pv_generation_kwh=pv,wind_generation_kwh=0.,renewable_generation_kwh=pv,
            grid_power_kwh=grid,storage_charge_kwh=charge,storage_discharge_kwh=discharge,
            storage_soc_kwh=soc,storage_soc_start_kwh=before,curtailment_kwh=curtail,
            carbon_emission_t=emission,green_power_carbon_reduction_t=(pv-curtail)*FACTOR_ELECTRICITY/1000,
            balance_error_kwh=demand-(pv+discharge+grid-charge-curtail))
        points.append(p)
    return points

def snapshot(db,site_id,at=None,history_hours=168):
    site=db.get(Site,site_id)
    if site is None:raise LookupError('园区不存在')
    if site.code!='HBUE':raise ValueError('该实时示范仅适用于湖北经济学院校园')
    buildings=db.scalars(select(Building).where(Building.site_id==site_id)).all()
    bound=[b for b in buildings if b.code in PROFILES and (b.metadata_json or {}).get('data_class')=='DEMO_SIMULATION']
    if not bound:raise ValueError('校园尚未绑定示范业务建筑')
    # Asset availability is derived from the existing campus metering topology.
    from app.models import MeteringPoint
    device_ids=db.scalars(select(MeteringPoint.device_id).where(MeteringPoint.site_id==site_id)).all()
    kinds=set(db.scalars(select(Device.device_type).where(Device.id.in_(device_ids))).all())
    now=(at or datetime.now(TZ)).astimezone(TZ)
    codes=tuple(sorted(b.code for b in bound))
    annual=_year(now.year,codes,'PV' in kinds,'STORAGE' in kinds,'EV_CHARGER' in kinds)
    index=int((now-datetime(now.year,1,1,tzinfo=TZ)).total_seconds()/3600)
    fraction=(now.minute*60+now.second)/3600
    past=annual[:index];current=dict(annual[index])
    current['timestamp']=now.isoformat()
    current['storage_soc_kwh']=current['storage_soc_start_kwh']+(current['storage_soc_kwh']-current['storage_soc_start_kwh'])*fraction
    # Full hour points are completed energy intervals; the live point is a rate
    # snapshot and is intentionally NOT added as a whole hour to energy totals.
    total=sum(p['carbon_emission_t'] for p in past)+annual[index]['carbon_emission_t']*fraction
    clean=sum(p['green_power_carbon_reduction_t'] for p in past)+annual[index]['green_power_carbon_reduction_t']*fraction
    months={}
    for p in past:months[p['timestamp'][:7]]=months.get(p['timestamp'][:7],0)+p['carbon_emission_t']
    months[now.isoformat()[:7]]=months.get(now.isoformat()[:7],0)+annual[index]['carbon_emission_t']*fraction
    ranks=[]
    # Allocate purchased electricity proportionally to each building's demand,
    # while gas stays with the canteen; EV belongs to the sports parking area.
    for b in bound:
        emission=0.;energy=water=gas_total=grid_total=0.;building_months={}
        for i in range(index+1):
            p=annual[i];t=datetime.fromisoformat(p['timestamp']);r=values(*PROFILES[b.code],t);weight=fraction if i==index else 1.
            demand=r['energy_kwh'][0]+(p['ev_charging_load_kwh'] if b.code=='HBUE-B003' else 0.)
            all_demand=p['load_after_saving_kwh']+p['ev_charging_load_kwh']
            allocated_grid=p['grid_power_kwh']*demand/all_demand*weight
            amount=(allocated_grid*FACTOR_ELECTRICITY+r['gas_m3'][0]*FACTOR_GAS*weight)/1000
            emission+=amount;grid_total+=allocated_grid
            month=p['timestamp'][:7];building_months[month]=building_months.get(month,0)+amount
            energy+=demand*weight;water+=r['water_m3'][0]*weight;gas_total+=r['gas_m3'][0]*weight
        live=values(*PROFILES[b.code],now)
        ranks.append(dict(id=b.id,building_id=b.code,campus_id='HBUE',floor_id=None,area_id=None,timestamp=now.isoformat(),
            name=b.name,emission_t=emission,energy_kwh=energy,water_m3=water,gas_m3=gas_total,grid_import_kwh=grid_total,
            scope1_t=gas_total*FACTOR_GAS/1000,scope2_t=grid_total*FACTOR_ELECTRICITY/1000,
            trend=[dict(timestamp=k,emission_t=v) for k,v in building_months.items()],
            power_kw=live['energy_kwh'][0],hvac_power_kw=live['hvac_power_kw'][0],lighting_power_kw=live['lighting_power_kw'][0]))
    return dict(site_id=site_id,campus_id='HBUE',timestamp=now.isoformat(),source_type='DEMO_SIMULATION',
        data_notice='示范仿真数据',model_version='HBUE-LIVE-1',period_start=f'{now.year}-01-01',
        factors={'electricity':dict(value=FACTOR_ELECTRICITY,unit='kgCO2e/kWh'),
            'natural_gas':dict(value=FACTOR_GAS,unit='kgCO2e/m3'),'source':'校园既有示范核算参数，非学校实测因子'},
        total_emission_t=total,clean_reduction_t=clean,trend=[dict(timestamp=k,emission_t=v) for k,v in months.items()],
        hourly=past[-history_hours:],current=current,buildings=ranks,
        limitations=['建筑轮廓为真实空间数据，能源数值为规则驱动仿真，非学校实测。',
            '光伏720千瓦、储能840千瓦时及排放因子沿用示范假设；校园未绑定风机，风电为零。',
            '累计指标为当年截至当前时间；已完成小时为千瓦时，当前负荷为千瓦。'],
        replacement_policy='仅对人工确认映射、时间和单位有效的真实指标替换；未映射设备不替换。')
