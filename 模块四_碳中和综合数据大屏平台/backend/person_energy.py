"""Display upstream occupancy/empty-energy results; never invent per-person shares."""
import math
def normalize(payload):
    report=payload.get('association',{}).get('report')
    cameras=payload.get('occupancy',{}).get('cameras',[])
    result={'task_id':payload['task_id'],'status':'AVAILABLE' if report else 'NO_REPORT',
            'cameras':cameras,'report':report,'personal_allocations':[],
            'notice':'上游接口结果；报告能源输入未核验为实测，不能标为真实电表数据。当前没有Global ID个人能耗分摊结果。',
            'raw_payload':payload,'metrics':[]}
    if not report:return result
    calc=report.get('calculation',{});summary=report.get('summary',{})
    for code,name,value,unit in [
        ('energy_delta','区间耗电增量',calc.get('active_energy_delta_kwh'),'kWh'),
        ('wasted_energy','空置浪费耗电估计',summary.get('estimated_wasted_energy_kwh'),'kWh'),
        ('wasted_carbon','空置浪费碳排估计',summary.get('estimated_carbon_kg'),'kgCO₂'),
        ('factor','报告排放因子',calc.get('emission_factor_kg_per_kwh'),'kgCO₂/kWh')]:
        result['metrics'].append({'code':code,'name':name,'value':value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) else None,'unit':unit})
    return result
