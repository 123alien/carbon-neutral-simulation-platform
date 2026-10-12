"""Run the P3-1 accounting → simulation → recommendation → report chain."""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

if os.getenv("ALLOW_SYNTHETIC_VALIDATION") != "1":
    raise RuntimeError("synthetic validation is disabled; set ALLOW_SYNTHETIC_VALIDATION=1 only in an isolated test environment")
os.environ.setdefault("APP_ENV","test")
os.environ.setdefault("DATABASE_URL","sqlite:///./validation_fixture.db")
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from sqlalchemy import func,select,update
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import CarbonMarketTimeseries, Enterprise

client=TestClient(app);DATA=ROOT/"demo_data"

def ok(r,label):
    if r.status_code>=300:raise RuntimeError(f"{label}: {r.status_code} {r.text[:1500]}")
    return r.json()

def ensure_validation_fixture():
    """Make the isolated validation command reproducible from an empty database."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        has_demo=db.scalar(select(func.count()).select_from(Enterprise).where(Enterprise.name=="智慧低碳示范园区")) or 0
    if not has_demo:
        from load_demo_case import main as load_demo_case
        load_demo_case()

def main():
    ensure_validation_fixture()
    enterprise=next(x for x in ok(client.get("/api/enterprises"),"enterprises") if x["name"]=="智慧低碳示范园区");eid=enterprise["id"]
    # Accounting: monthly electricity (Scope 2) and natural gas (Scope 1).
    existing=ok(client.get("/api/carbon-accounting/runs",params={"enterprise_id":eid}),"accounting history")
    accounting=next((x for x in existing if x["name"]=="DEMO-2024 园区统一碳核算 V3"),None)
    if not accounting:
        device_rows=ok(client.get("/api/devices",params={"enterprise_id":eid}),"devices")
        device_ids={x["external_id"]:x["id"] for x in device_rows}
        building_codes=["METER-B01","METER-B02","METER-B03","METER-B04"]
        month_load={(code,m):0.0 for code in building_codes for m in range(1,13)}
        metric_rows=csv.DictReader((DATA/"device_metrics_2024.csv").open(encoding="utf-8-sig"))
        for row in metric_rows:
            code=row["device_external_id"]
            if row["metric_name"]!="power_kw":continue
            month=datetime.fromisoformat(row["timestamp"]).month
            if code in building_codes:month_load[(code,month)]+=float(row["value"])
        gas_rows=list(csv.DictReader((DATA/"natural_gas_2024.csv").open(encoding="utf-8-sig")))
        activities=[]
        for (code,m),value in month_load.items():activities.append({"timestamp":f"2024-{m:02d}-15T12:00:00+08:00","energy_type":"electricity","value":value,"unit":"kWh","scope":"SCOPE_2","device_id":device_ids[code],"source":f"DEMO_SIMULATION/{code}"})
        for row in gas_rows:
            month=datetime.fromisoformat(row["month"]).month
            activities.append({"timestamp":f"2024-{month:02d}-15T12:00:00+08:00","energy_type":"natural_gas","value":float(row["natural_gas_m3"]),"unit":"m3","scope":"SCOPE_1","device_id":device_ids["METER-MAIN"],"source":"DEMO_SIMULATION/natural_gas"})
        accounting=ok(client.post("/api/carbon-accounting/runs",json={"enterprise_id":eid,"name":"DEMO-2024 园区统一碳核算 V3","period_start":"2024-01-01T00:00:00+08:00","period_end":"2025-01-01T00:00:00+08:00","scopes":["SCOPE_1","SCOPE_2"],"standard_basis":"示范仿真核算口径 / GHG Protocol / ISO 14064-1","activities":activities}),"accounting")
    accounting_results=ok(client.get(f"/api/carbon-accounting/runs/{accounting['id']}/results"),"accounting results")

    scenarios=ok(client.get("/api/scenarios",params={"enterprise_id":eid}),"scenarios")
    def pv(capacity,capex):return {"measure_type":"PV","start_year":2024,"parameters_json":{"capacity_kw":capacity,"performance_ratio":.82,"tilt_deg":25,"azimuth_deg":180,"inverter_efficiency":.97,"irradiance_mode":"GHI","noct_c":45,"temperature_coefficient_per_c":-.004,"capex":capex}}
    def wind():return {"measure_type":"WIND","start_year":2024,"parameters_json":{"rated_power_kw":120,"cut_in_speed_m_s":3,"rated_speed_m_s":10,"cut_out_speed_m_s":25,"capex":0}}
    def storage(capacity,power,capex):return {"measure_type":"STORAGE","start_year":2024,"parameters_json":{"capacity_kwh":capacity,"max_charge_kw":power,"max_discharge_kw":power,"charge_efficiency":.95,"discharge_efficiency":.95,"soc_initial":.5,"soc_min":.1,"soc_max":.9,"strategy":"PV_SELF_CONSUMPTION","capex":capex}}
    specs={
      "BASELINE":[pv(420,0),wind(),storage(480,120,0)],
      "ECONOMIC":[pv(600,720000),wind(),storage(480,120,0),{"measure_type":"LIGHTING","start_year":2024,"parameters_json":{"saving_rate":.25,"load_share":.16,"capex":120000}}],
      "REDUCTION":[pv(840,1680000),wind(),storage(960,240,960000),{"measure_type":"HVAC","start_year":2024,"parameters_json":{"saving_rate":.16,"load_share":.34,"capex":420000}},{"measure_type":"GREEN_POWER","start_year":2024,"parameters_json":{"purchase_share":.3,"emission_factor_kg_per_kwh":0,"premium_per_kwh":.06,"capex":0}}],
      "BALANCED":[pv(720,1200000),wind(),storage(840,220,720000),{"measure_type":"HVAC","start_year":2024,"parameters_json":{"saving_rate":.12,"load_share":.34,"capex":300000}},{"measure_type":"LIGHTING","start_year":2024,"parameters_json":{"saving_rate":.25,"load_share":.16,"capex":120000}}]
    }
    scenario_map={x["scenario_type"]:x for x in scenarios if x["name"].startswith("DEMO-")}
    def normalized_measures(items):
        return [{k:v for k,v in item.items() if not (k=="end_year" and v is None)} for item in items]
    for kind,measures in specs.items():
        if kind not in scenario_map:
            scenario_map[kind]=ok(client.post("/api/scenarios",json={"enterprise_id":eid,"name":f"DEMO-{kind}-2024","description":"DEVELOPMENT/DEMO/VALIDATION scenario","base_year":2024,"start_year":2024,"end_year":2024,"target_peak_year":2030,"target_neutral_year":2060,"baseline_growth_json":{},"status":"ACTIVE","scenario_type":kind,"measures":measures}),f"scenario {kind}")
        else:
            scenario=scenario_map[kind]
            versions=ok(client.get(f"/api/scenarios/{scenario['id']}/versions"),f"versions {kind}")
            current=next(x for x in versions if x["id"]==scenario["current_version_id"])
            if normalized_measures(current["parameter_snapshot_json"].get("measures",[]))!=normalized_measures(measures):
                version=ok(client.post(f"/api/scenarios/{scenario['id']}/versions",json={"name":scenario["name"],"description":"统一示范园区场景；现有光伏、风电和储能已计入基准","base_year":2024,"start_year":2024,"end_year":2024,"target_peak_year":2030,"target_neutral_year":2060,"baseline_growth_json":{},"status":"ACTIVE","scenario_type":kind,"measures":measures}),f"update scenario {kind}")
                scenario["current_version_id"]=version["id"]

    balanced_version=scenario_map["BALANCED"]["current_version_id"]
    market_scenario=client.get(f"/api/carbon-market/scenarios/{balanced_version}")
    if market_scenario.status_code==404:
        market_scenario=client.post("/api/carbon-market/scenarios",json={"scenario_version_id":balanced_version,"carbon_price_per_t":82,"carbon_quota_t":2200,"ccer_quantity_t":250,"ccer_price_per_t":54,"green_certificate_quantity":500,"green_certificate_price":6.5})
    ok(market_scenario,"market scenario")
    with SessionLocal() as db:market_count=db.scalar(select(func.count()).select_from(CarbonMarketTimeseries).where(CarbonMarketTimeseries.region=="DEMO_REGION")) or 0
    if not market_count:
        rows=list(csv.DictReader((DATA/"carbon_market_2024.csv").open(encoding="utf-8-sig")))
        items=[{"region":"DEMO_REGION","timestamp":x["timestamp"],"carbon_price_per_t":float(x["carbon_price_per_t"]),"carbon_quota_t":float(x["carbon_quota_t"]),"trading_volume_t":float(x["trading_volume_t"]),"ccer_volume_t":200,"ccer_price_per_t":float(x["ccer_price_per_t"]),"green_certificate_volume":500,"green_certificate_price":float(x["green_certificate_price"]),"source":"DEMO_SIMULATION"} for x in rows]
        ok(client.post("/api/carbon-market/indicators/bulk",json={"items":items}),"market indicators")
    else:
        with SessionLocal() as db:
            db.execute(update(CarbonMarketTimeseries).where(CarbonMarketTimeseries.region=="DEMO_REGION").values(source="DEMO_SIMULATION"));db.commit()

    batches=ok(client.get("/api/simulation/batches",params={"enterprise_id":eid}),"batches")
    batch=next((x for x in batches if set(i["scenario_version_id"] for i in x["items"])==set(scenario_map[k]["current_version_id"] for k in specs)),None)
    if not batch:
        batch=ok(client.post("/api/simulation/batches",json={"enterprise_id":eid,"scenario_version_ids":[scenario_map[k]["current_version_id"] for k in specs],"baseline_scenario_version_id":scenario_map["BASELINE"]["current_version_id"],"year":2024,"electricity_price_per_kwh":.72,"feed_in_tariff_per_kwh":.38,"store_hourly_results":True}),"simulation batch")
    balanced_item=next(x for x in batch["items"] if x["scenario_version_id"]==balanced_version);task_id=balanced_item["task_id"]

    recs=ok(client.get("/api/recommendations/low-carbon-paths",params={"enterprise_id":eid}),"recommendations")
    recommendation=next((x for x in recs if x["simulation_year"]==2024),None)
    if not recommendation:recommendation=ok(client.post("/api/recommendations/low-carbon-paths",json={"enterprise_id":eid,"simulation_year":2024,"target_peak_year":2030,"target_neutral_year":2060,"carbon_quota_t":2200,"energy_target_kwh":4300000,"budget":2500000,"top_n":3}),"recommendation")

    costs=ok(client.get("/api/carbon-market/assessments",params={"scenario_version_id":balanced_version,"task_id":task_id}),"costs")
    cost=costs[0] if costs else ok(client.post("/api/carbon-market/assessments",json={"scenario_version_id":balanced_version,"task_id":task_id}),"carbon cost")
    risks=ok(client.get("/api/risk-assessments",params={"scenario_version_id":balanced_version,"simulation_task_id":task_id}),"risks")
    risk=risks[0] if risks else ok(client.post("/api/risk-assessments",json={"scenario_version_id":balanced_version,"simulation_task_id":task_id,"batch_item_id":balanced_item["id"],"simulation_year":2024,"price_volatility_pct":18,"renewable_volatility_pct":15,"technical_implementation_score":.72}),"risk")
    reports=ok(client.get("/api/reports",params={"scenario_version_id":balanced_version,"simulation_task_id":task_id}),"reports")
    report=next((x for x in reports if x["title"]=="智慧低碳示范园区碳中和综合报告（统一口径）"),None)
    if not report:report=ok(client.post("/api/reports/feasibility",json={"enterprise_id":eid,"scenario_version_id":balanced_version,"simulation_task_id":task_id,"title":"智慧低碳示范园区碳中和综合报告（统一口径）","batch_id":batch["id"],"accounting_run_id":accounting["id"],"recommendation_run_id":recommendation["id"]}),"report")
    if not report.get("files") or {x["format"] for x in report["files"]}!={"DOCX","PDF"}:
        files=ok(client.post(f"/api/reports/{report['id']}/render",json={"formats":["DOCX","PDF"]}),"render report")
    else:files=report["files"]
    scopes={};energies={}
    for x in accounting_results:scopes[x["scope"]]=scopes.get(x["scope"],0)+x["emission_t"];energies[x["energy_type"]]=energies.get(x["energy_type"],0)+x["emission_t"]
    result={"enterprise_id":eid,"accounting":{"id":accounting["id"],"total_t":accounting["summary_json"]["total_emission_t"],"by_scope":scopes,"by_energy":energies},"scenarios":{k:{"id":v["id"],"version_id":v["current_version_id"]} for k,v in scenario_map.items()},"batch":{"id":batch["id"],"status":batch["status"],"items":batch["items"],"comparison":batch["comparison_json"]},"recommendation":{"id":recommendation["id"],"count":len(recommendation["recommendations"])},"carbon_cost":{"id":cost["id"],"result":cost["result_json"]},"risk":{"id":risk["id"],"overall":risk["overall_level"],"count":len(risk["results"])},"report":{"id":report["id"],"files":files}}
    (DATA/"full_chain_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"accounting_total_t":result["accounting"]["total_t"],"batch_id":batch["id"],"batch_status":batch["status"],"recommendations":result["recommendation"]["count"],"risk":result["risk"],"report_id":report["id"],"files":[{"format":x["format"],"size":x["file_size"]} for x in files]},ensure_ascii=False))

if __name__=="__main__":main()
