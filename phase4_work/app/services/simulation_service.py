from datetime import datetime
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Enterprise, SimulationTask, SimulationYearResult
from app.schemas.simulation import SimulationRunRequest
from app.services.scenario_service import get_scenario, get_version, ensure_version
from app.services.energy_service import resolve_emission_factor, annual_energy_totals, estimate_growth
from app.simulation.types import SimulationState, ScenarioConfig
from app.simulation.economics import EconomicEvaluator
from app.simulation.orchestrator import SimulationOrchestrator
from app.simulation.measures.pv import PhotovoltaicModel
from app.simulation.measures.hvac import HVACSavingModel
from app.simulation.measures.lighting import LightingSavingModel
from app.simulation.unit_conversion import UnitConverter

SUPPORTED_ENERGY = ("electricity", "natural_gas", "coal", "oil")

def _run_campus_annual(db,req,scenario,version,spec,site):
    from app.services.long_term_path_service import run_long_term_path
    from app.schemas.long_term import LongTermPathRequest
    raw=(spec.baseline_growth_json or {}).get('electricity',0.)
    growth=float(raw) if not isinstance(raw,str) else 0.
    path=run_long_term_path(db,LongTermPathRequest(site_id=site.id,scenario_version_id=version.id,start_year=spec.base_year,end_year=spec.end_year,target_peak_year=spec.target_peak_year or 2030,target_neutral_year=spec.target_neutral_year or 2060,annual_load_growth_rate=growth,annual_grid_factor_change_rate=0,annual_price_change_rate=0,electricity_price_per_kwh=req.electricity_price_per_kwh,neutrality_threshold_t=req.neutrality_epsilon_t))
    result=path.result_snapshot_json;baseline=path.input_snapshot_json['unified_baseline']
    gas=baseline['scope1_t']*1000/2.162
    task=SimulationTask(scenario_id=scenario.id,scenario_version_id=version.id,status='SUCCESS',started_at=datetime.utcnow(),finished_at=datetime.utcnow(),parameter_snapshot_json={'simulation_mode':'ANNUAL','site_id':site.id,'year':spec.base_year,'unified_baseline':baseline,'scenario_version':version.parameter_snapshot_json,'long_term_path_run_id':path.id},carbon_market_snapshot_json=version.carbon_market_snapshot_json if hasattr(version,'carbon_market_snapshot_json') else None,summary_json={'name':spec.name,'peak_year':result['actual_peak_year'],'neutral_year':result['actual_neutral_year'],'cumulative_emission_t':sum(r['net_emission_t'] for r in result['annual']),'cumulative_investment':result['cumulative_investment'],'cumulative_benefit':sum(baseline['metrics']['grid_power_kwh']*(1+growth)**(r['year']-spec.base_year)*req.electricity_price_per_kwh-r['operating_cost'] for r in result['annual']),'data_notice':'示范仿真数据','long_term_path_run_id':path.id,'baseline_checksum':baseline['checksum'],'limitations':result['limitations']})
    db.add(task);db.flush()
    for row in result['annual']:
        if row['year']<spec.start_year:continue
        gross=baseline['metrics']['load_base_kwh']*(1+growth)**(row['year']-spec.base_year)
        db.add(SimulationYearResult(task_id=task.id,scenario_id=scenario.id,year=row['year'],electricity_base_kwh=gross,electricity_after_saving_kwh=row['energy_consumption_kwh'],grid_power_kwh=row['grid_import_kwh'],natural_gas_m3=gas*(1+growth)**(row['year']-spec.base_year),pv_generation_kwh=row['pv_generation_kwh'],energy_saved_kwh=max(gross-row['energy_consumption_kwh'],0),carbon_emission_t=row['net_emission_t'],carbon_reduction_t=row['carbon_reduction_t'],investment=row['annual_investment']))
    db.commit();db.refresh(task);return task


def _year_energy_total(db: Session, enterprise_id: int, year: int, energy_type: str) -> float:
    values = dict(annual_energy_totals(db, enterprise_id, energy_type))
    return float(values.get(year, 0.0))


def _build_measure(m):
    p = dict(m.parameters_json or {})
    common = {"start_year": m.start_year, "end_year": m.end_year}
    if m.measure_type == "PV":
        return PhotovoltaicModel(
            **common,
            capacity_kw=float(p["capacity_kw"]),
            annual_irradiation_kwh_per_kw=float(p["annual_irradiation_kwh_per_kw"]),
            system_efficiency=float(p.get("system_efficiency", 0.85)),
            degradation_rate=float(p.get("degradation_rate", 0.007)),
            capex=float(p.get("capex", 0.0)),
            opex_per_year=float(p.get("opex_per_year", 0.0)),
        )
    if m.measure_type == "HVAC":
        return HVACSavingModel(
            **common,
            load_share=float(p["load_share"]), saving_rate=float(p["saving_rate"]),
            capex=float(p.get("capex", 0.0)), opex_per_year=float(p.get("opex_per_year", 0.0)),
        )
    if m.measure_type == "LIGHTING":
        return LightingSavingModel(
            **common,
            quantity=int(p["quantity"]), power_before_w=float(p["power_before_w"]),
            power_after_w=float(p["power_after_w"]), annual_hours=float(p["annual_hours"]),
            capex=float(p.get("capex", 0.0)), opex_per_year=float(p.get("opex_per_year", 0.0)),
        )
    raise ValueError(f"Unsupported measure_type: {m.measure_type}")


def _resolve_growth_rates(db: Session, enterprise_id: int, raw: dict) -> tuple[dict[str, float], dict[str, str]]:
    rates: dict[str, float] = {}
    sources: dict[str, str] = {}
    raw = raw or {}
    for energy_type in SUPPORTED_ENERGY:
        configured = raw.get(energy_type, "auto" if energy_type in {"electricity", "natural_gas"} else 0.0)
        if isinstance(configured, str) and configured.lower() == "auto":
            est = estimate_growth(db, enterprise_id, energy_type, "median_yoy")
            rates[energy_type] = float(est["rate"])
            sources[energy_type] = f"auto:median_yoy:{est['years_used']}"
        else:
            rates[energy_type] = float(configured or 0.0)
            sources[energy_type] = "configured"
    return rates, sources


def _factor_provider(db: Session, region: str | None):
    expected_units = {
        "electricity": "kgCO2/kWh",
        "natural_gas": "kgCO2/m3",
        "coal": "kgCO2/kg",
        "oil": "kgCO2/kg",
    }

    def provider(year: int) -> dict[str, float]:
        factors: dict[str, float] = {}
        for energy_type in SUPPORTED_ENERGY:
            obj = resolve_emission_factor(db, region, year, energy_type)
            if obj is None:
                factors[energy_type] = 0.0
                continue
            expected = expected_units[energy_type].lower().replace(" ", "")
            actual = obj.unit.lower().replace(" ", "")
            if actual != expected:
                raise ValueError(
                    f"emission factor unit mismatch for {energy_type}: {obj.unit}; expected {expected_units[energy_type]}"
                )
            factors[energy_type] = float(obj.factor)
        if factors.get("electricity", 0.0) <= 0:
            raise ValueError(f"electricity emission factor not found for simulation year {year}")
        return factors

    return provider


def run_simulation(db: Session, req: SimulationRunRequest) -> SimulationTask:
    from app.services.carbon_market_analysis_service import market_snapshot
    scenario = get_scenario(db, req.scenario_id)
    if scenario is None:
        raise LookupError("scenario not found")
    version=get_version(db,req.scenario_version_id) if req.scenario_version_id else ensure_version(db,scenario)
    if version is None or version.scenario_id!=scenario.id:raise ValueError("scenario version does not belong to scenario")
    version_snapshot=version.parameter_snapshot_json
    spec=SimpleNamespace(**{key:version_snapshot.get(key,getattr(scenario,key)) for key in ["name","base_year","start_year","end_year","target_peak_year","target_neutral_year","baseline_growth_json"]})
    spec.measures=[SimpleNamespace(**item) for item in version_snapshot.get("measures",[])]
    enterprise = db.get(Enterprise, scenario.enterprise_id)
    if enterprise is None:
        raise LookupError("enterprise not found")

    from app.services.campus_simulation_input import resolve_site
    site=resolve_site(db,enterprise.id,getattr(req,'site_id',None) or version_snapshot.get('site_id'))
    if site and site.code=='HBUE':return _run_campus_annual(db,req,scenario,version,spec,site)
    base = {e: _year_energy_total(db, enterprise.id, spec.base_year, e) for e in SUPPORTED_ENERGY}
    if base["electricity"] <= 0:
        raise ValueError("base-year electricity data is required and must be > 0")

    growth_rates, growth_sources = _resolve_growth_rates(db, enterprise.id, spec.baseline_growth_json or {})
    factor_provider = _factor_provider(db, enterprise.region)
    base_factors = factor_provider(spec.base_year)

    snapshot = {
        "scenario_id": scenario.id,
        "scenario_version_id":version.id,
        "scenario_version":version.parameter_snapshot_json,
        "carbon_market":market_snapshot(db,version.id),
        "enterprise_id": enterprise.id,
        "base_year": spec.base_year,
        "base_energy": {e: {"value": base[e], "unit": UnitConverter.canonical_unit(e)} for e in SUPPORTED_ENERGY},
        "base_emission_factors": base_factors,
        "growth_rates": growth_rates,
        "growth_sources": growth_sources,
        "measures": [
            {"type": m.measure_type, "start_year": m.start_year, "end_year": m.end_year, "parameters": m.parameters_json}
            for m in spec.measures
        ],
    }
    task = SimulationTask(scenario_id=scenario.id, scenario_version_id=version.id, status="RUNNING", parameter_snapshot_json=snapshot, carbon_market_snapshot_json=market_snapshot(db,version.id), risk_parameter_snapshot_json=version.risk_parameter_snapshot_json,
                          started_at=datetime.utcnow())
    db.add(task); db.commit(); db.refresh(task)

    try:
        measures = [_build_measure(m) for m in spec.measures]
        config = ScenarioConfig(
            name=spec.name,
            start_year=spec.start_year,
            end_year=spec.end_year,
            growth_rates=growth_rates,
            target_peak_year=spec.target_peak_year,
            target_neutral_year=spec.target_neutral_year,
            neutrality_epsilon_t=req.neutrality_epsilon_t,
            peak_stability_years=req.peak_stability_years,
            neutrality_stability_years=req.neutrality_stability_years,
        )
        runner = SimulationOrchestrator(
            factor_provider,
            EconomicEvaluator(req.electricity_price_per_kwh, req.feed_in_tariff_per_kwh),
        )
        initial = SimulationState(
            year=spec.base_year,
            electricity_base_kwh=base["electricity"],
            natural_gas_m3=base["natural_gas"],
            coal_kg=base["coal"],
            oil_kg=base["oil"],
        )
        summary = runner.run(initial, config, measures)
        baseline_summary = runner.run(initial, config, [])
        baseline_by_year = {s.year: s.carbon_emission_t for s in baseline_summary.states}

        for s in summary.states:
            db.add(SimulationYearResult(
                task_id=task.id, scenario_id=scenario.id, year=s.year,
                electricity_base_kwh=s.electricity_base_kwh,
                electricity_after_saving_kwh=s.electricity_after_saving_kwh,
                grid_power_kwh=s.grid_power_kwh,
                natural_gas_m3=s.natural_gas_m3,
                coal_kg=s.coal_kg,
                oil_kg=s.oil_kg,
                pv_generation_kwh=s.pv_generation_kwh,
                pv_self_use_kwh=s.pv_self_use_kwh,
                pv_export_kwh=s.pv_export_kwh,
                energy_saved_kwh=s.energy_saved_kwh,
                carbon_emission_t=s.carbon_emission_t,
                carbon_reduction_t=max(baseline_by_year.get(s.year, s.carbon_emission_t) - s.carbon_emission_t, 0.0),
                investment=s.investment,
                annual_benefit=s.annual_benefit,
            ))

        task.summary_json = {
            "name": summary.name,
            "peak_year": summary.peak_year,
            "neutral_year": summary.neutral_year,
            "target_peak_year": spec.target_peak_year,
            "target_neutral_year": spec.target_neutral_year,
            "peak_year_delta": None if summary.peak_year is None or spec.target_peak_year is None else summary.peak_year - spec.target_peak_year,
            "neutral_year_delta": None if summary.neutral_year is None or spec.target_neutral_year is None else summary.neutral_year - spec.target_neutral_year,
            "cumulative_emission_t": summary.cumulative_emission_t,
            "cumulative_investment": summary.cumulative_investment,
            "cumulative_benefit": summary.cumulative_benefit,
            "growth_rates": growth_rates,
            "growth_sources": growth_sources,
        }
        task.status = "SUCCESS"
        task.finished_at = datetime.utcnow()
        db.commit(); db.refresh(task)
        return task
    except Exception as exc:
        db.rollback()
        task = db.get(SimulationTask, task.id)
        task.status = "FAILED"
        task.error_message = str(exc)
        task.finished_at = datetime.utcnow()
        db.commit(); db.refresh(task)
        raise


def get_task_result(db: Session, task_id: int):
    task = db.get(SimulationTask, task_id)
    if task is None:
        return None, []
    results = list(db.scalars(select(SimulationYearResult).where(SimulationYearResult.task_id == task_id)
                              .order_by(SimulationYearResult.year)).all())
    return task, results


def compare_scenarios(db: Session, scenario_ids: list[int], req_kwargs: dict) -> list[dict]:
    if len(scenario_ids) < 2:
        raise ValueError("at least two scenario_ids are required")
    items: list[dict] = []
    for scenario_id in scenario_ids:
        task = run_simulation(db, SimulationRunRequest(scenario_id=scenario_id, **req_kwargs))
        summary = task.summary_json or {}
        items.append({
            "scenario_id": scenario_id,
            "task_id": task.id,
            "name": summary.get("name", ""),
            "peak_year": summary.get("peak_year"),
            "neutral_year": summary.get("neutral_year"),
            "cumulative_emission_t": float(summary.get("cumulative_emission_t", 0.0)),
            "cumulative_investment": float(summary.get("cumulative_investment", 0.0)),
            "cumulative_benefit": float(summary.get("cumulative_benefit", 0.0)),
        })
    items.sort(key=lambda x: x["cumulative_emission_t"])
    return items
