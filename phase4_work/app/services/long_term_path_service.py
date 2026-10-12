from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models import Enterprise, LoadTimeseries, LongTermPathRun, Scenario, ScenarioVersion, SimulationTask
from app.schemas.long_term import LongTermPathRequest, StrengthenedPathRequest
from app.services.energy_service import resolve_emission_factor

def _number(data: dict | None, *keys: str, default: float = 0.0) -> float:
    data = data or {}
    for key in keys:
        value = data.get(key)
        if value is not None:
            try: return float(value)
            except (TypeError, ValueError): pass
    return default

def _baseline(db: Session, enterprise: Enterprise, version: ScenarioVersion, req: LongTermPathRequest):
    from app.services.campus_simulation_input import resolve_site,restore
    site=resolve_site(db,enterprise.id,req.site_id or version.parameter_snapshot_json.get('site_id'))
    if site and site.code=='HBUE':
        task=db.get(SimulationTask,req.baseline_task_id) if req.baseline_task_id else None
        if task is None and req.baseline_task_id:raise ValueError('指定的园区基准任务不存在')
        if task is None:
            from app.services.hourly_simulation_service import run_hourly_simulation
            from app.schemas.hourly import HourlySimulationRunRequest
            task,_,_=run_hourly_simulation(db,HourlySimulationRunRequest(scenario_id=version.scenario_id,scenario_version_id=version.id,site_id=site.id,year=req.start_year,temporary_measures=[],store_hourly_results=False))
        frozen=(task.parameter_snapshot_json or {}).get('unified_baseline')
        if task.status!='SUCCESS' or task.scenario_version_id!=version.id or not frozen:raise ValueError('请选择该园区场景的统一基准任务；旧任务需重新运行')
        restore(frozen)
        if frozen['provenance']['site_id']!=site.id or frozen['provenance']['year']!=req.start_year:raise ValueError('园区基准的园区或年度与长期推演不一致')
        summary=frozen['metrics']
        return task,summary['load_base_kwh'],summary['renewable_generation_kwh'],summary['grid_power_kwh'],summary['carbon_emission_t']
    task = db.get(SimulationTask, req.baseline_task_id) if req.baseline_task_id else None
    if task and (task.scenario_version_id != version.id or task.status != "SUCCESS"):
        raise ValueError("baseline task must be a successful task of the selected scenario version")
    if task is None:
        task = db.scalar(select(SimulationTask).where(
            SimulationTask.scenario_version_id == version.id, SimulationTask.status == "SUCCESS"
        ).order_by(SimulationTask.finished_at.desc(), SimulationTask.id.desc()))
    summary = task.summary_json if task else {}
    start = datetime(req.start_year, 1, 1); end = datetime(req.start_year + 1, 1, 1)
    measured = db.scalar(select(func.sum(LoadTimeseries.load_kwh)).where(
        LoadTimeseries.enterprise_id == enterprise.id, LoadTimeseries.timestamp >= start, LoadTimeseries.timestamp < end
    )) or 0.0
    energy = _number(summary, "load_base_kwh", "total_energy_kwh", default=float(measured))
    if energy <= 0: raise ValueError("baseline annual energy is unavailable")
    renewable = _number(summary, "renewable_generation_kwh", default=0.0)
    grid = _number(summary, "grid_power_kwh", "grid_import_kwh", default=max(energy - renewable, 0.0))
    emission = _number(summary, "carbon_emission_t", "total_emission_tco2e", default=0.0)
    return task, energy, renewable, grid, emission

def _gap_analysis(req, annual, measures, neutral, peak, base_scope1):
    target_row=next((x for x in annual if x["year"]==req.target_neutral_year),annual[-1])
    peak_delay=max(peak["year"]-req.target_peak_year,0)
    neutral_gap=max(target_row["net_emission_t"]-req.neutrality_threshold_t,0.0)
    quota_gaps=[{"year":x["year"],"gap_t":max(-x["quota_balance_t"],0.0)} for x in annual if x["quota_balance_t"]<0]
    active={m["measure_type"] for m in measures}; late_cutoff=req.start_year+10
    late_renewable=any(m["measure_type"] in {"PV","WIND"} and m["start_year"]>late_cutoff for m in measures)
    late_efficiency=any(m["measure_type"] in {"HVAC","LIGHTING"} and m["start_year"]>late_cutoff for m in measures)
    green=max((_number(m["parameters_json"],"purchase_share","green_ratio") for m in measures if m["measure_type"]=="GREEN_POWER"),default=0.0)
    ccer=sum((_number(m["parameters_json"],"annual_offset_t","quantity_t") for m in measures if m["measure_type"]=="CCER"),0.0)
    end=annual[-1];renewable_ratio=end["renewable_generation_kwh"]/end["energy_consumption_kwh"] if end["energy_consumption_kwh"] else 0
    reasons=[]
    def add(code,title,evidence): reasons.append({"code":code,"title":title,"evidence":evidence})
    if req.annual_load_growth_rate>0:add("LOAD_GROWTH","园区负荷持续增长",f"年度负荷增长率为{req.annual_load_growth_rate*100:.2f}%，期末能源消费量较基准增加{(end['energy_consumption_kwh']/annual[0]['energy_consumption_kwh']-1)*100:.2f}%。")
    if req.annual_grid_factor_change_rate>=-req.annual_load_growth_rate:add("GRID_FACTOR","电网排放因子下降速度不足",f"电网排放因子年变化率为{req.annual_grid_factor_change_rate*100:.2f}%，不足以抵消负荷增长及剩余购电排放。")
    if renewable_ratio<.5:add("RENEWABLE_SCALE","可再生能源容量不足",f"期末可再生能源发电量占能源消费量约{renewable_ratio*100:.2f}%。")
    if not late_renewable and {"PV","WIND"}&active:add("NO_LATE_EXPANSION","可再生能源后续扩容不足",f"{late_cutoff}年后没有新的光伏或风电投产计划。")
    if not late_efficiency and {"HVAC","LIGHTING"}&active:add("NO_DEEP_EFFICIENCY","节能改造缺少后续深化",f"{late_cutoff}年后没有新增空调或照明深化改造计划。")
    if "STORAGE" in active and neutral_gap>0:add("STORAGE_LIMIT","储能对净碳排贡献有限","储能改善消纳和峰谷运行，但不直接产生零碳电量，当前路径仍存在排放缺口。")
    if green<.8 and neutral_gap>0:add("GREEN_POWER","绿电采购比例不足",f"当前长期措施中的最高绿电采购比例为{green*100:.2f}%。")
    if ccer<neutral_gap and neutral_gap>0:add("CCER","抵消资源不足",f"目标年可用抵消量为{ccer:.2f}吨，低于{neutral_gap:.2f}吨中和缺口。")
    if base_scope1>req.neutrality_threshold_t:add("DIRECT_EMISSION","剩余直接排放缺少替代措施",f"基准直接排放约{base_scope1:.2f}吨，当前路径未完全消除。")
    met=peak_delay==0 and neutral is not None and neutral<=req.target_neutral_year
    if met:
        success=[]
        if renewable_ratio>=.5:success.append("可再生能源覆盖率达到较高水平")
        if green>=.8:success.append("高比例绿电采购有效降低剩余间接排放")
        if late_efficiency:success.append("节能措施按阶段持续深化")
        if not success:success.append("当前措施组合与排放因子演化共同满足目标")
        recommendations=[]
    else:
        near=[];mid=[];far=[]
        if any(r["code"] in {"LOAD_GROWTH","NO_DEEP_EFFICIENCY"} for r in reasons):near.append("优先深化空调、照明等重点用能系统节能改造，并建立年度能源与碳排复核机制。")
        if any(r["code"] in {"RENEWABLE_SCALE","NO_LATE_EXPANSION"} for r in reasons):near.append("完成第一阶段光伏扩容，并根据场地条件核查风电增容可行性。")
        if any(r["code"] in {"RENEWABLE_SCALE","NO_LATE_EXPANSION","STORAGE_LIMIT"} for r in reasons):mid.append("根据负荷增长持续扩建光伏、风电和储能，提升可再生能源自用比例并优化储能调度。")
        if any(r["code"]=="GREEN_POWER" for r in reasons):mid.append("逐步提高绿电采购比例，明确合同电量、期限和碳属性边界。")
        if any(r["code"]=="DIRECT_EMISSION" for r in reasons):far.append("对剩余直接排放源实施电气化或低碳能源替代。")
        if any(r["code"]=="CCER" for r in reasons):far.append("对难以消除的剩余排放，在完成实质减排后合理配置CCER等抵消资源。")
        far.append("依据年度目标缺口滚动调整措施规模，避免将目标年份直接视为实际达成年份。")
        recommendations=[{"stage":"近期阶段","items":near},{"stage":"中期阶段","items":mid},{"stage":"远期阶段","items":far}]
        success=[]
    return {"targets_met":met,"target_peak_year":req.target_peak_year,"actual_peak_year":peak["year"],"peak_delay_years":peak_delay,
        "target_neutral_year":req.target_neutral_year,"actual_neutral_year":neutral,"target_year_remaining_emission_t":target_row["net_emission_t"],
        "neutrality_gap_t":neutral_gap,"neutrality_threshold_t":req.neutrality_threshold_t,"annual_quota_gaps":quota_gaps,
        "max_quota_gap_t":max((x["gap_t"] for x in quota_gaps),default=0.0),"reasons":reasons,"recommendations":recommendations,"success_factors":success}

def run_long_term_path(db: Session, req: LongTermPathRequest) -> LongTermPathRun:
    version = db.get(ScenarioVersion, req.scenario_version_id)
    if not version: raise LookupError("scenario version not found")
    scenario = db.get(Scenario, version.scenario_id); enterprise = db.get(Enterprise, scenario.enterprise_id) if scenario else None
    if not scenario or not enterprise: raise LookupError("scenario enterprise not found")
    task, base_energy, base_renewable, base_grid, base_emission = _baseline(db, enterprise, version, req)
    frozen=(task.parameter_snapshot_json or {}).get('unified_baseline') if task else None
    factor_row = resolve_emission_factor(db, enterprise.region, req.start_year, "electricity")
    base_factor = req.grid_factor_kg_per_kwh or (frozen['factor'] if frozen else (float(factor_row.factor) if factor_row else None))
    if not base_factor or base_factor <= 0: raise ValueError("baseline grid emission factor is unavailable")
    base_scope1 = frozen['scope1_t'] if frozen else max(base_emission - base_grid * base_factor / 1000, 0.0)
    raw_measures = req.measures
    if raw_measures is None:
        measures = [{"measure_type": str(m.get("measure_type", "")).upper(),
                     "start_year": int(m.get("start_year", req.start_year)), "end_year": m.get("end_year"),
                     "parameters_json": dict(m.get("parameters_json") or {})}
                    for m in (version.parameter_snapshot_json or {}).get("measures", [])]
    else:
        measures = [{"measure_type": m.measure_type.upper(), "start_year": m.start_year, "end_year": m.end_year,
                     "parameters_json": dict(m.parameters_json or {})} for m in raw_measures]
    annual=[]; cumulative_investment=0.0; cumulative_reduction=0.0
    for year in range(req.start_year, req.end_year + 1):
        elapsed=year-req.start_year; gross_energy=base_energy*((1+req.annual_load_growth_rate)**elapsed)
        saving_rate=0.0; added_renewable=0.0; added_pv=0.0; green_ratio=0.0; ccer_t=0.0; annual_investment=0.0; milestones=[]
        for measure in measures:
            if year < measure["start_year"] or (measure["end_year"] is not None and year > measure["end_year"]): continue
            p=measure["parameters_json"]; kind=measure["measure_type"]
            if year == measure["start_year"]:
                annual_investment += _number(p,"capex","investment","investment_yuan")
                milestones.append(kind)
            annual_investment += _number(p,"annual_addition_kw")*_number(p,"capex_per_kw")
            if kind in {"HVAC","LIGHTING"}: saving_rate += _number(p,"saving_rate")*_number(p,"load_share",default=1.0)
            elif kind == "PV":
                capacity=_number(p,"capacity_kw","capacity_kwp","installed_capacity_kwp")+_number(p,"annual_addition_kw")*(year-measure["start_year"]+1)
                pv_yield=capacity*_number(p,"annual_yield_kwh_per_kw","annual_irradiation_kwh_per_kw",default=1100)*_number(p,"performance_ratio","system_efficiency",default=0.8)
                added_renewable+=pv_yield;added_pv+=pv_yield
            elif kind == "WIND":
                capacity=_number(p,"rated_power_kw","capacity_kw")+_number(p,"annual_addition_kw")*(year-measure["start_year"]+1)
                added_renewable += capacity*8760*_number(p,"capacity_factor",default=0.22)
            elif kind == "STORAGE":
                # Storage shifts energy and improves renewable self-use; it is not generation.
                if not frozen:added_renewable *= 1 + min(_number(p,"renewable_utilization_gain",default=0.02),0.1)
            elif kind == "GREEN_POWER": green_ratio=max(green_ratio,_number(p,"purchase_share","green_ratio"))
            elif kind == "CCER": ccer_t += _number(p,"annual_offset_t","quantity_t")
        saving_rate=min(max(saving_rate,0.0),0.8)
        energy=max(gross_energy*(1-saving_rate),0.0); renewable=max(base_renewable+added_renewable,0.0)
        storage_loss=(base_grid-base_energy+base_renewable)*((1+req.annual_load_growth_rate)**elapsed) if frozen else 0.
        grid=max(energy-renewable+storage_loss,0.0); green_kwh=min(grid,max(green_ratio,0.0)*grid)
        factor=base_factor*((1+req.annual_grid_factor_change_rate)**elapsed)
        gross_emission=base_scope1*((1+req.annual_load_growth_rate)**elapsed)+grid*factor/1000
        green_reduction=green_kwh*factor/1000; net=max(gross_emission-green_reduction-ccer_t,0.0)
        baseline_emission=(base_scope1+base_grid*base_factor/1000)*((1+req.annual_load_growth_rate)**elapsed)
        reduction=max(baseline_emission-net,0.0); quota=req.carbon_quota_t*((1+req.annual_quota_change_rate)**elapsed)
        quota_balance=quota-net; price=req.electricity_price_per_kwh*((1+req.annual_price_change_rate)**elapsed)
        operating_cost=grid*price; carbon_cost=max(-quota_balance,0.0)*req.carbon_price_per_t + ccer_t*req.carbon_price_per_t
        cumulative_investment += annual_investment; cumulative_reduction += reduction
        annual.append({"year":year,"energy_consumption_kwh":energy,"renewable_generation_kwh":renewable,
            "grid_import_kwh":grid,"gross_emission_t":gross_emission,"net_emission_t":net,
            "carbon_reduction_t":reduction,"reduction_rate":reduction/baseline_emission if baseline_emission else 0.0,
            "carbon_quota_t":quota,"quota_balance_t":quota_balance,"annual_investment":annual_investment,
            "cumulative_investment":cumulative_investment,"operating_cost":operating_cost,"carbon_cost":carbon_cost,
            "grid_factor_kg_per_kwh":factor,"commissioned_measures":milestones,
            "pv_generation_kwh":(frozen['metrics']['pv_generation_kwh'] if frozen else base_renewable)+added_pv})
    if frozen:
        _anchor_first_year(frozen,measures,req,annual[0],base_factor,base_emission)
        cumulative_reduction=sum(x['carbon_reduction_t'] for x in annual)
    peak=max(annual,key=lambda x:x["net_emission_t"]); neutral=next((x["year"] for x in annual if x["net_emission_t"]<=req.neutrality_threshold_t),None)
    gap_analysis=_gap_analysis(req,annual,measures,neutral,peak,base_scope1)
    result={"annual":annual,"actual_peak_year":peak["year"],"peak_emission_t":peak["net_emission_t"],
        "actual_neutral_year":neutral,"neutrality_status":"ACHIEVED" if neutral else f"{req.end_year}年前未实现碳中和",
        "target_peak_met":peak["year"]<=req.target_peak_year,"target_neutral_met":neutral is not None and neutral<=req.target_neutral_year,
        "comprehensive_energy_target_met":None if req.comprehensive_energy_target_rate is None else annual[-1]["energy_consumption_kwh"]<=base_energy*(1-req.comprehensive_energy_target_rate),
        "emission_at_end_t":annual[-1]["net_emission_t"],"cumulative_reduction_t":cumulative_reduction,
        "cumulative_investment":annual[-1]["cumulative_investment"],"cumulative_energy_cost":sum(x["operating_cost"] for x in annual),
        "gap_analysis":gap_analysis,
        "key_milestones":[{"year":x["year"],"measures":x["commissioned_measures"]} for x in annual if x["commissioned_measures"]],
        "baseline":{"energy_kwh":base_energy,"renewable_kwh":base_renewable,"grid_import_kwh":base_grid,"emission_t":base_emission,
                    "grid_factor_kg_per_kwh":base_factor,"parameter_source":"CURRENT_SCENARIO_AND_HOURLY_BASELINE"}}
    frozen=req.model_dump(); frozen["resolved_measures"]=measures
    if task and task.parameter_snapshot_json.get('unified_baseline'):
        frozen['unified_baseline']=task.parameter_snapshot_json['unified_baseline']
        frozen['site_id']=frozen['unified_baseline']['provenance']['site_id']
        result['baseline']['checksum']=frozen['unified_baseline']['checksum']
        result['data_notice']='示范仿真数据'
        result['limitations']=['首年使用冻结小时输入完整运行；后续年度为状态演化近似。','储能不增加发电量；后续沿用基准储能购电差额，新增调度效果须小时模型复核。']
    run=LongTermPathRun(enterprise_id=enterprise.id,scenario_version_id=version.id,baseline_task_id=task.id if task else None,
        status="SUCCESS",input_snapshot_json=frozen,result_snapshot_json=result)
    db.add(run);db.commit();db.refresh(run);return run

def get_long_term_path(db:Session,run_id:int): return db.get(LongTermPathRun,run_id)

def _anchor_first_year(frozen,measures,req,row,factor,base_emission):
    from app.services.campus_simulation_input import restore,combine
    from app.services.hourly_simulation_service import _snapshot_measure_config
    from app.simulation.hourly import HourlySimulationEngine
    points=restore(frozen);changes=_snapshot_measure_config({'measures':measures})
    from app.simulation.green_power import GreenPowerAllocator
    from datetime import timedelta
    green=changes.get('green_power');allocator=None
    if green and HourlySimulationEngine._active(green,points[0].timestamp):
        allocator=GreenPowerAllocator([{'start_at':points[0].timestamp,'end_at':points[-1].timestamp+timedelta(hours=1),'purchase_share':green.get('purchase_share'),'purchase_kwh':green.get('purchase_kwh'),'emission_factor_kg_per_kwh':green.get('emission_factor_kg_per_kwh',0),'premium_per_kwh':green.get('premium_per_kwh',0)}])
    _,first=HourlySimulationEngine(factor,req.electricity_price_per_kwh).run(points,combine(frozen['existing_config'],changes),allocator)
    offsets=sum(_number(m['parameters_json'],'annual_offset_t','quantity_t') for m in measures if m['measure_type']=='CCER' and m['start_year']<=req.start_year and (m['end_year'] is None or m['end_year']>=req.start_year))
    net=max(first.carbon_emission_t-offsets,0);reduction=max(base_emission-net,0)
    row.update(energy_consumption_kwh=first.load_base_kwh-first.energy_saved_kwh,renewable_generation_kwh=first.renewable_generation_kwh,grid_import_kwh=first.grid_power_kwh,gross_emission_t=first.carbon_emission_t+first.green_power_carbon_reduction_t,net_emission_t=net,quota_balance_t=row['carbon_quota_t']-net,operating_cost=first.electricity_cost,carbon_reduction_t=reduction,reduction_rate=reduction/base_emission if base_emission else 0)
    row['carbon_cost']=max(-row['quota_balance_t'],0)*req.carbon_price_per_t+offsets*req.carbon_price_per_t
    row['pv_generation_kwh']=first.pv_generation_kwh

def list_long_term_paths(db:Session,enterprise_id:int,limit:int=20):
    return list(db.scalars(select(LongTermPathRun).where(LongTermPathRun.enterprise_id==enterprise_id).order_by(LongTermPathRun.id.desc()).limit(limit)).all())

def strengthen_long_term_path(db:Session,source_run_id:int,data:StrengthenedPathRequest):
    source=db.get(LongTermPathRun,source_run_id)
    if source is None:raise LookupError("long-term path run not found")
    payload=dict(source.input_snapshot_json);payload["source_run_id"]=source.id
    measures=list(payload.get("resolved_measures") or payload.get("measures") or [])
    start=int(payload["start_year"]);middle=min(start+10,int(payload["end_year"]))
    if data.pv_annual_addition_kw:measures.append({"measure_type":"PV","start_year":start+1,"parameters_json":{"annual_addition_kw":data.pv_annual_addition_kw,"annual_yield_kwh_per_kw":1100,"performance_ratio":.8,"capex_per_kw":3500,"cost_source":"FUNCTION_PARAMETER_ONLY"}})
    if data.wind_annual_addition_kw:measures.append({"measure_type":"WIND","start_year":start+1,"parameters_json":{"annual_addition_kw":data.wind_annual_addition_kw,"capacity_factor":.22,"capex_per_kw":7000,"cost_source":"FUNCTION_PARAMETER_ONLY"}})
    if data.storage_expansion_kwh:measures.append({"measure_type":"STORAGE","start_year":data.storage_expansion_year or middle,"parameters_json":{"capacity_kwh":data.storage_expansion_kwh,"renewable_utilization_gain":.04,"capex":0}})
    if data.additional_hvac_saving_rate:measures.append({"measure_type":"HVAC","start_year":middle,"parameters_json":{"saving_rate":data.additional_hvac_saving_rate,"load_share":1,"capex":0}})
    if data.additional_lighting_saving_rate:measures.append({"measure_type":"LIGHTING","start_year":middle,"parameters_json":{"saving_rate":data.additional_lighting_saving_rate,"load_share":1,"capex":0}})
    if data.green_power_ratio:measures.append({"measure_type":"GREEN_POWER","start_year":middle,"parameters_json":{"purchase_share":data.green_power_ratio}})
    if data.annual_ccer_t:measures.append({"measure_type":"CCER","start_year":middle,"parameters_json":{"annual_offset_t":data.annual_ccer_t}})
    payload["measures"]=measures;payload.pop("resolved_measures",None);payload["baseline_task_id"]=source.baseline_task_id
    if data.annual_grid_factor_change_rate is not None:payload["annual_grid_factor_change_rate"]=data.annual_grid_factor_change_rate
    return run_long_term_path(db,LongTermPathRequest.model_validate(payload))
