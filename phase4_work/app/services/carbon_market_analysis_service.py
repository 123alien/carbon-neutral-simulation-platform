from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.market_analysis import CarbonCostEngine, RiskAssessmentEngine, ReportEngine
from app.models import (CarbonMarketScenario,CarbonMarketTimeseries,CarbonCostAssessment,RiskAssessmentRun,RiskAssessmentResult,
 ReportTask,ReportSnapshot,ScenarioVersion,SimulationTask,SimulationBatchItem,SimulationBatch,CarbonAccountingRun,CarbonAccountingResult,
 PathRecommendationRun,PathRecommendation,Enterprise,RiskAssessmentResult,ReportFile,Site,DataSource,LongTermPathRun)

def market_snapshot(db:Session,version_id:int):
    row=db.scalar(select(CarbonMarketScenario).where(CarbonMarketScenario.scenario_version_id==version_id))
    if not row:return None
    return {k:getattr(row,k) for k in ("carbon_price_per_t","carbon_quota_t","ccer_quantity_t","ccer_price_per_t","green_certificate_quantity","green_certificate_price")}

def create_market_scenario(db:Session,data):
    version=db.get(ScenarioVersion,data.scenario_version_id)
    if version is None:raise LookupError("scenario version not found")
    if market_snapshot(db,data.scenario_version_id) is not None:raise ValueError("carbon market scenario for this immutable version already exists")
    snapshot={k:v for k,v in data.model_dump().items() if k!="scenario_version_id"};version.carbon_market_snapshot_json=snapshot
    row=CarbonMarketScenario(**data.model_dump());db.add(row);db.commit();db.refresh(row);return row

def get_market_scenario(db:Session,version_id:int):
    row=db.scalar(select(CarbonMarketScenario).where(CarbonMarketScenario.scenario_version_id==version_id))
    if row is None:raise LookupError("carbon market scenario not found")
    return row

def add_indicators(db:Session,data):
    rows=[CarbonMarketTimeseries(**item.model_dump()) for item in data.items];db.add_all(rows);db.commit();return {"inserted":len(rows)}

def statistics(db:Session,region,start,end):
    q=select(CarbonMarketTimeseries).where(CarbonMarketTimeseries.region==region)
    if start:q=q.where(CarbonMarketTimeseries.timestamp>=start)
    if end:q=q.where(CarbonMarketTimeseries.timestamp<end)
    rows=list(db.scalars(q.order_by(CarbonMarketTimeseries.timestamp)).all())
    fields=("carbon_price_per_t","carbon_quota_t","trading_volume_t","trading_amount_yuan","ccer_volume_t","ccer_price_per_t","ccer_trading_amount_yuan","green_certificate_volume","green_certificate_price","green_certificate_issued_count","green_certificate_traded_count")
    result={}
    for f in fields:
        vals=[getattr(r,f) for r in rows if getattr(r,f) is not None]
        result[f]={"count":len(vals),"sum":sum(vals) if vals else None,"average":sum(vals)/len(vals) if vals else None,"min":min(vals) if vals else None,"max":max(vals) if vals else None}
    record_fields=("carbon_price_per_t","carbon_quota_t","trading_volume_t","trading_amount_yuan","ccer_volume_t","ccer_price_per_t","ccer_trading_amount_yuan","green_certificate_volume","green_certificate_price","green_certificate_issued_count","green_certificate_traded_count")
    return {"region":region,"start":start,"end":end,"record_count":len(rows),"indicators":result,"quality":"COMPLETE" if rows else "NO_DATA","records":[{"id":r.id,"region":r.region,"timestamp":r.timestamp,"source":r.source,**{field:getattr(r,field) for field in record_fields}} for r in rows]}

def assess_cost(db:Session,data):
    if db.get(ScenarioVersion,data.scenario_version_id) is None:raise LookupError("scenario version not found")
    gross=data.gross_emission_t
    task=db.get(SimulationTask,data.task_id)
    if task is None:raise LookupError("simulation task not found")
    if task.scenario_version_id!=data.scenario_version_id:raise ValueError("task and scenario version mismatch")
    gross=float((task.summary_json or {}).get("carbon_emission_t",0)) if gross is None else gross
    snapshot=task.carbon_market_snapshot_json
    if snapshot is None:raise ValueError("simulation task has no frozen carbon market snapshot")
    result=CarbonCostEngine.calculate(gross,snapshot)
    row=CarbonCostAssessment(scenario_version_id=data.scenario_version_id,task_id=data.task_id,gross_emission_t=gross,input_snapshot_json={"gross_emission_t":gross,"market":snapshot},result_json=result)
    db.add(row);db.commit();db.refresh(row);return row

def get_cost(db,id):
    row=db.get(CarbonCostAssessment,id)
    if row is None:raise LookupError("carbon cost assessment not found")
    return row

def list_costs(db,scenario_version_id=None,task_id=None,limit=100):
    stmt=select(CarbonCostAssessment)
    if scenario_version_id is not None:stmt=stmt.where(CarbonCostAssessment.scenario_version_id==scenario_version_id)
    if task_id is not None:stmt=stmt.where(CarbonCostAssessment.task_id==task_id)
    return list(db.scalars(stmt.order_by(CarbonCostAssessment.created_at.desc(),CarbonCostAssessment.id.desc()).limit(limit)).all())

def assess_risk(db:Session,data):
    version=db.get(ScenarioVersion,data.scenario_version_id)
    if version is None:raise LookupError("scenario version not found")
    task=db.get(SimulationTask,data.simulation_task_id)
    if task is None:raise LookupError("simulation task not found")
    if task.scenario_version_id!=version.id:raise ValueError("simulation task and scenario version mismatch")
    inputs=data.model_dump();inputs.update({"target_peak_year":version.parameter_snapshot_json.get("target_peak_year"),"target_neutral_year":version.parameter_snapshot_json.get("target_neutral_year")})
    if data.batch_item_id:
        item=db.get(SimulationBatchItem,data.batch_item_id)
        if item is None:raise LookupError("simulation batch item not found")
        if item.scenario_version_id!=data.scenario_version_id:raise ValueError("batch item and scenario version mismatch")
        m=item.metrics_json or {}
        for key in ("reduction_rate","payback_years"):inputs[key]=getattr(data,key) if getattr(data,key) is not None else m.get(key)
        batch=db.get(SimulationBatch,item.batch_id);inputs["simulation_year"]=data.simulation_year or (batch.request_snapshot_json or {}).get("year")
    result=RiskAssessmentEngine.assess(inputs)
    version.risk_parameter_snapshot_json=dict(inputs);task.risk_parameter_snapshot_json=dict(inputs)
    row=RiskAssessmentRun(scenario_version_id=data.scenario_version_id,simulation_task_id=data.simulation_task_id,batch_item_id=data.batch_item_id,input_snapshot_json=inputs,overall_level=result["overall_level"])
    db.add(row);db.flush()
    db.add_all([RiskAssessmentResult(run_id=row.id,risk_category=r["category"],risk_level=r["level"],indicator_value_json=r["indicator_value"],trigger_reason=r["trigger_reason"],recommendation=r["recommendation"]) for r in result["risks"]]);db.commit();db.refresh(row);return _risk_response(db,row)

def _risk_response(db,row):
    results=list(db.scalars(select(RiskAssessmentResult).where(RiskAssessmentResult.run_id==row.id).order_by(RiskAssessmentResult.id)).all())
    return {"id":row.id,"scenario_version_id":row.scenario_version_id,"simulation_task_id":row.simulation_task_id,"batch_item_id":row.batch_item_id,"input_snapshot_json":row.input_snapshot_json,"overall_level":row.overall_level,"created_at":row.created_at,"results":[{"category":r.risk_category,"level":r.risk_level,"indicator_value":r.indicator_value_json,"trigger_reason":r.trigger_reason,"recommendation":r.recommendation} for r in results]}

def get_risk(db,id):
    row=db.get(RiskAssessmentRun,id)
    if row is None:raise LookupError("risk assessment not found")
    return _risk_response(db,row)

def list_risks(db,scenario_version_id=None,simulation_task_id=None,start=None,end=None,limit=100):
    stmt=select(RiskAssessmentRun)
    if scenario_version_id is not None:stmt=stmt.where(RiskAssessmentRun.scenario_version_id==scenario_version_id)
    if simulation_task_id is not None:stmt=stmt.where(RiskAssessmentRun.simulation_task_id==simulation_task_id)
    if start is not None:stmt=stmt.where(RiskAssessmentRun.created_at>=start)
    if end is not None:stmt=stmt.where(RiskAssessmentRun.created_at<end)
    rows=db.scalars(stmt.order_by(RiskAssessmentRun.created_at.desc(),RiskAssessmentRun.id.desc()).limit(limit)).all()
    return [_risk_response(db,row) for row in rows]

def batch_market_comparison(db,batch_id):
    batch=db.get(SimulationBatch,batch_id)
    if batch is None:raise LookupError("simulation batch not found")
    items=(batch.comparison_json or {}).get("items",[])
    return {"batch_id":batch.id,"baseline_scenario_version_id":batch.baseline_scenario_version_id,"items":[{"scenario_version_id":item.get("scenario_version_id"),"task_id":item.get("task_id"),"carbon_market_result":item.get("carbon_market_result")} for item in items]}

def create_report(db:Session,data):
    from app.services.model_validation_service import summaries as model_validation_summaries
    enterprise=db.get(Enterprise,data.enterprise_id)
    if enterprise is None:raise LookupError("enterprise not found")
    version=db.get(ScenarioVersion,data.scenario_version_id);task=db.get(SimulationTask,data.simulation_task_id)
    if version is None:raise LookupError("scenario version not found")
    if task is None:raise LookupError("simulation task not found")
    if task.scenario_version_id!=version.id:raise ValueError("simulation task and scenario version mismatch")
    from app.models import Scenario
    owner=db.get(Scenario,version.scenario_id)
    if not owner or owner.enterprise_id!=enterprise.id:raise ValueError('报告场景不属于当前单位')
    unified=(task.parameter_snapshot_json or {}).get('unified_baseline')
    if unified:
        from app.services.campus_simulation_input import restore
        restore(unified)
        if data.accounting_run_id:raise ValueError('该校园报告使用冻结统一基准核算，请取消旧年度核算批次，避免混用时间口径')
    batch=db.get(SimulationBatch,data.batch_id) if data.batch_id else None
    accounting=db.get(CarbonAccountingRun,data.accounting_run_id) if data.accounting_run_id else None
    recommendation=db.get(PathRecommendationRun,data.recommendation_run_id) if data.recommendation_run_id else None
    if data.batch_id and batch is None:raise LookupError("simulation batch not found")
    if data.accounting_run_id and accounting is None:raise LookupError("accounting run not found")
    if data.recommendation_run_id and recommendation is None:raise LookupError("recommendation run not found")
    version_ids=[]
    batch_data=None
    if batch:
        version_ids=[i.scenario_version_id for i in db.scalars(select(SimulationBatchItem).where(SimulationBatchItem.batch_id==batch.id))]
        batch_data={"id":batch.id,"status":batch.status,"comparison_json":batch.comparison_json,"request_snapshot_json":batch.request_snapshot_json}
    costs=list(db.scalars(select(CarbonCostAssessment).where(CarbonCostAssessment.scenario_version_id.in_(version_ids))).all()) if version_ids else []
    risks=list(db.scalars(select(RiskAssessmentRun).where(RiskAssessmentRun.scenario_version_id==version.id,RiskAssessmentRun.simulation_task_id==task.id)).all())
    accounting_data=None
    if accounting:
        details=list(db.scalars(select(CarbonAccountingResult).where(CarbonAccountingResult.run_id==accounting.id)).all());annual={};by_energy={};by_scope={};activity_by_energy={}
        for x in details:
            annual[str(x.timestamp.year)]=annual.get(str(x.timestamp.year),0)+x.emission_t;by_energy[x.energy_type]=by_energy.get(x.energy_type,0)+x.emission_t;by_scope[x.scope]=by_scope.get(x.scope,0)+x.emission_t
            key=(x.energy_type,x.activity_unit);activity_by_energy[key]=activity_by_energy.get(key,0)+x.activity_value
        activities=[{"energy_type":energy,"activity_value":value,"activity_unit":unit,"emission_t":by_energy.get(energy,0),"scope":next((x.scope for x in details if x.energy_type==energy),None),"factor_sources":sorted({x.factor_source for x in details if x.energy_type==energy and x.factor_source}),"factor_versions":sorted({x.factor_version for x in details if x.energy_type==energy and x.factor_version})} for (energy,unit),value in activity_by_energy.items()]
        accounting_data={"id":accounting.id,"model_version":"CarbonAccountingModel/ENERGY-V1","summary":{**(accounting.summary_json or {}),"annual_emissions":annual,"by_energy":by_energy,"by_scope":by_scope,"activity_by_energy":activities},"factor_sources":sorted({x.factor_source for x in details if x.factor_source}),"result_count":len(details)}
    recs=list(db.scalars(select(PathRecommendation).where(PathRecommendation.run_id==recommendation.id).order_by(PathRecommendation.profile,PathRecommendation.rank)).all()) if recommendation else []
    recommendation_data={"id":recommendation.id,"input":recommendation.input_snapshot_json,"baseline":recommendation.baseline_summary_json,"paths":[{"id":x.id,"profile":x.profile,"rank":x.rank,"score":x.score,"measures":x.measures_json,"reasons":x.reasons_json,"metrics":x.metrics_json} for x in recs]} if recommendation else None
    long_term=db.scalar(select(LongTermPathRun).where(LongTermPathRun.scenario_version_id==version.id).order_by(LongTermPathRun.id.desc()))
    if unified:
        if recommendation and (recommendation.input_snapshot_json.get('unified_baseline') or {}).get('checksum')!=unified['checksum']:raise ValueError('推荐与报告的园区基准快照不一致')
        if batch:
            members=db.scalars(select(SimulationBatchItem).where(SimulationBatchItem.batch_id==batch.id)).all()
            for member in members:
                member_task=db.get(SimulationTask,member.task_id) if member.task_id else None
                if member_task and (member_task.parameter_snapshot_json.get('unified_baseline') or {}).get('checksum')!=unified['checksum']:raise ValueError('批量仿真与报告的基准快照不一致')
        long_term=next((r for r in db.scalars(select(LongTermPathRun).where(LongTermPathRun.scenario_version_id==version.id).order_by(LongTermPathRun.id.desc())) if (r.input_snapshot_json.get('unified_baseline') or {}).get('checksum')==unified['checksum']),None)
        m=unified['metrics'];s1=unified['scope1_t'];s2=m['carbon_emission_t']-s1;year=str(unified['provenance']['year'])
        accounting_data={'id':None,'model_version':unified['model_version'],'summary':{'total_emission_t':m['carbon_emission_t'],'total_emission_tco2e':m['carbon_emission_t'],'annual_emissions':{year:m['carbon_emission_t']},'by_scope':{'SCOPE_1':s1,'SCOPE_2':s2},'by_energy':{'electricity':s2,'natural_gas':s1},'activity_by_energy':[{'energy_type':'electricity','activity_value':m['grid_power_kwh'],'activity_unit':'kWh','emission_t':s2},{'energy_type':'natural_gas','activity_value':s1*1000/2.162,'activity_unit':'m3','emission_t':s1}]},'factor_sources':['校园冻结示范核算参数'],'baseline_checksum':unified['checksum'],'data_notice':'示范仿真数据'}
    long_term_data={"run_id":long_term.id,"input":long_term.input_snapshot_json,"result":long_term.result_snapshot_json,"created_at":long_term.created_at.isoformat()} if long_term else None
    risk_data=[]
    for x in risks:
        detail=list(db.scalars(select(RiskAssessmentResult).where(RiskAssessmentResult.run_id==x.id)).all());risk_data.append({"id":x.id,"scenario_version_id":x.scenario_version_id,"simulation_task_id":x.simulation_task_id,"overall_level":x.overall_level,"results":[{"category":r.risk_category,"level":r.risk_level,"indicator_value":r.indicator_value_json,"trigger_reason":r.trigger_reason,"recommendation":r.recommendation} for r in detail]})
    sites=list(db.scalars(select(Site).where(Site.enterprise_id==enterprise.id).order_by(Site.id)).all())
    data_sources=list(db.scalars(select(DataSource).where(DataSource.enterprise_id==enterprise.id).order_by(DataSource.id)).all())
    public_sources=[]
    for source in data_sources:
        config=source.config_json or {}
        if config.get("data_class") in {"REAL_PUBLIC","REAL_PUBLIC_OFFICIAL"}:
            public_sources.append({"data_source_id":source.id,"name":source.name,"data_class":config.get("data_class"),"dataset_id":config.get("dataset_id"),"source_url":config.get("source_url"),"source_type":source.source_type})
    public_sites=[]
    for site in sites:
        metadata=site.metadata_json or {}
        if metadata.get("data_class") in {"REAL_PUBLIC","REAL_PUBLIC_OFFICIAL"}:
            public_sites.append({"site_id":site.id,"name":site.name,"data_class":metadata.get("data_class"),"dataset_id":metadata.get("dataset_id"),"publisher":metadata.get("publisher"),"source_url":metadata.get("source_url"),"geographic_precision":metadata.get("geographic_precision")})
    data_provenance={"classification":"公开真实数据" if public_sites or public_sources else "未声明","sites":public_sites,"data_sources":public_sources,"time_range":{"start":(task.parameter_snapshot_json or {}).get("start_time"),"end":(task.parameter_snapshot_json or {}).get("end_time")},"limitations":["公开研究数据不代表目标企业内部实测数据","模型仿真输出不等同于历史实测结果","缺失数据未补零、未插值，质量口径以冻结快照和导入清单为准"] if public_sites or public_sources else []}
    if unified:data_provenance={'classification':'示范仿真数据','site_id':unified['provenance']['site_id'],'baseline_checksum':unified['checksum'],'time_range':{'start':unified['inputs'][0]['timestamp'],'end':unified['inputs'][-1]['timestamp']},'limitations':['真实校园空间底图；能源为校园规则仿真，非学校实测。','现状核算为无新增措施的冻结基准；场景结果为在其上实施措施后的结果。','长期首年为小时模型，后续为年度近似。']}
    sources={"project":{"enterprise_id":enterprise.id,"name":enterprise.name,"region":enterprise.region,"industry":enterprise.industry,"building_area":enterprise.building_area,"population":enterprise.population},"energy_and_devices":{"simulation_snapshot":task.parameter_snapshot_json},"scenario_batch":batch_data,"long_term_path":long_term_data,"carbon_accounting":accounting_data,"path_recommendations":recommendation_data,"carbon_market":[{"id":x.id,"scenario_version_id":x.scenario_version_id,"input_snapshot":x.input_snapshot_json,"result":x.result_json} for x in costs],"risk_assessments":risk_data,"model_validation":model_validation_summaries(),"data_provenance":data_provenance,"provenance":{"scenario_version_id":version.id,"simulation_task_id":task.id,"long_term_path_run_id":long_term.id if long_term else None,"batch_id":data.batch_id,"accounting_run_id":data.accounting_run_id,"recommendation_run_id":data.recommendation_run_id,"generated_at":datetime.utcnow().isoformat()+"Z"}}
    report=ReportTask(enterprise_id=data.enterprise_id,scenario_version_id=version.id,simulation_task_id=task.id,batch_id=data.batch_id,accounting_run_id=data.accounting_run_id,recommendation_run_id=data.recommendation_run_id,title=data.title,status="PENDING");db.add(report);db.flush();snapshot=ReportSnapshot(report_task_id=report.id,scenario_version_id=version.id,simulation_task_id=task.id,input_snapshot_json={"scenario_version":version.parameter_snapshot_json,"simulation_task":task.parameter_snapshot_json,"long_term_path":long_term.input_snapshot_json if long_term else None,"carbon_market":task.carbon_market_snapshot_json,"risk_parameters":task.risk_parameter_snapshot_json},report_data_json=ReportEngine.generate(data.title,sources));db.add(snapshot);db.commit();db.refresh(report);return _report_response(db,report)

def _report_response(db,row):
    snapshot=db.scalar(select(ReportSnapshot).where(ReportSnapshot.report_task_id==row.id))
    files=list(db.scalars(select(ReportFile).where(ReportFile.report_task_id==row.id).order_by(ReportFile.format)).all())
    return {"id":row.id,"enterprise_id":row.enterprise_id,"scenario_version_id":row.scenario_version_id,"simulation_task_id":row.simulation_task_id,"batch_id":row.batch_id,"accounting_run_id":row.accounting_run_id,"recommendation_run_id":row.recommendation_run_id,"title":row.title,"status":row.status,"failure_reason":row.failure_reason,"generated_at":row.generated_at,"input_snapshot_json":snapshot.input_snapshot_json,"report_data_json":snapshot.report_data_json,"snapshot_created_at":snapshot.created_at,"files":[{"id":x.id,"report_task_id":x.report_task_id,"format":x.format,"file_name":x.file_name,"file_size":x.file_size,"checksum":x.checksum,"generated_at":x.generated_at} for x in files],"created_at":row.created_at}

def get_report(db,id):
    row=db.get(ReportTask,id)
    if row is None:raise LookupError("feasibility report not found")
    return _report_response(db,row)

def list_reports(db,site_id=None,scenario_version_id=None,simulation_task_id=None,status=None,start=None,end=None,limit=100):
    stmt=select(ReportTask)
    if site_id is not None:
        site=db.get(Site,site_id)
        if site is None:raise LookupError("site not found")
        stmt=stmt.where(ReportTask.enterprise_id==site.enterprise_id)
    if scenario_version_id is not None:stmt=stmt.where(ReportTask.scenario_version_id==scenario_version_id)
    if simulation_task_id is not None:stmt=stmt.where(ReportTask.simulation_task_id==simulation_task_id)
    if status is not None:stmt=stmt.where(ReportTask.status==status)
    if start is not None:stmt=stmt.where(ReportTask.created_at>=start)
    if end is not None:stmt=stmt.where(ReportTask.created_at<end)
    rows=db.scalars(stmt.order_by(ReportTask.created_at.desc(),ReportTask.id.desc()).limit(limit)).all()
    return [_report_response(db,row) for row in rows]
