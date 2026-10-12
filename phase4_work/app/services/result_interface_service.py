"""Read-only carbon-neutrality results for a future unified presentation layer."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Building, CarbonCostAssessment, CarbonMarketTimeseries, Device, DeviceMetric,
    LongTermPathRun, MeteringPoint, Scenario, SimulationTask, Site,
)

DATA_CLASS = "DEMO_SIMULATION"
DATA_NOTICE = "示范仿真数据"


def _site(db: Session, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise LookupError("园区不存在")
    return site


def _campus_id(site: Site) -> str:
    return str((site.metadata_json or {}).get("campus_id") or site.code)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _building_meta(building: Building) -> dict:
    return building.metadata_json or {}


def _building_id(building: Building) -> str:
    return str(_building_meta(building).get("building_id") or building.code)


def _devices_by_building(db: Session, site_id: int) -> dict[int, list[Device]]:
    rows = db.execute(
        select(MeteringPoint.building_id, Device)
        .join(Device, Device.id == MeteringPoint.device_id)
        .where(MeteringPoint.site_id == site_id, MeteringPoint.building_id.is_not(None))
    ).all()
    grouped: dict[int, dict[int, Device]] = {}
    for building_id, device in rows:
        grouped.setdefault(building_id, {})[device.id] = device
    return {key: list(value.values()) for key, value in grouped.items()}


def _latest_metrics(db: Session, devices: list[Device]) -> tuple[datetime | None, dict[str, DeviceMetric]]:
    if not devices:
        return None, {}
    rows = list(db.scalars(
        select(DeviceMetric).where(DeviceMetric.device_id.in_([d.id for d in devices]))
        .order_by(DeviceMetric.timestamp.desc(), DeviceMetric.id.desc())
    ).all())
    latest: dict[str, DeviceMetric] = {}
    for row in rows:
        latest.setdefault(row.metric_name, row)
    return (rows[0].timestamp if rows else None), latest


def _metric_sum(db: Session, devices: list[Device], names: set[str]) -> float | None:
    if not devices:
        return None
    rows = list(db.scalars(select(DeviceMetric).where(
        DeviceMetric.device_id.in_([d.id for d in devices]), DeviceMetric.metric_name.in_(names)
    )).all())
    return sum(row.value for row in rows) if rows else None


def _hotspot_level(value: float | None, values: list[float]) -> str | None:
    if value is None or not values:
        return None
    ordered = sorted(values)
    high = ordered[max(0, int(len(ordered) * .75) - 1)]
    medium = ordered[max(0, int(len(ordered) * .40) - 1)]
    return "高" if value >= high else "中" if value >= medium else "低"


def campus_overview(db: Session, site_id: int) -> dict:
    site = _site(db, site_id)
    buildings = list(db.scalars(select(Building).where(Building.site_id == site.id).order_by(Building.id)).all())
    totals = {
        "electricity": sum(float(_building_meta(x).get("annual_energy_kwh") or 0) for x in buildings),
        "water": sum(float(_building_meta(x).get("annual_water_m3") or 0) for x in buildings),
        "gas": sum(float(_building_meta(x).get("annual_gas_m3") or 0) for x in buildings),
        "carbon": sum(float(_building_meta(x).get("annual_emission_tco2e") or 0) for x in buildings),
    }
    ranked = sorted(buildings, key=lambda x: float(_building_meta(x).get("annual_emission_tco2e") or 0), reverse=True)
    all_devices = [d for values in _devices_by_building(db, site.id).values() for d in values]
    storage = [d for d in all_devices if d.device_type == "STORAGE"]
    pv = [d for d in all_devices if d.device_type == "PV"]
    _, storage_latest = _latest_metrics(db, storage)
    return {
        "campus_id": _campus_id(site), "building_id": None, "floor_id": None, "area_id": None,
        "timestamp": _now(), "campus_name": site.name,
        "annual_electricity_kwh": totals["electricity"] or None,
        "annual_water_m3": totals["water"] or None,
        "annual_natural_gas_m3": totals["gas"] or None,
        "annual_carbon_emission_tco2e": totals["carbon"] or None,
        "photovoltaic_generation_kwh": _metric_sum(db, pv, {"generation_kwh", "energy_kwh"}),
        "storage_soc_pct": storage_latest.get("soc_pct").value if storage_latest.get("soc_pct") else None,
        "building_count": len(buildings),
        "hotspot_buildings": [{"building_id": _building_id(x), "building_name": x.name,
            "carbon_emission_tco2e": _building_meta(x).get("annual_emission_tco2e")} for x in ranked[:5]],
        "data_class": (site.metadata_json or {}).get("data_class", DATA_CLASS),
        "data_notice": (site.metadata_json or {}).get("data_notice", DATA_NOTICE),
    }


def building_results(db: Session, site_id: int) -> dict:
    site = _site(db, site_id)
    buildings = list(db.scalars(select(Building).where(Building.site_id == site.id).order_by(Building.code)).all())
    devices = _devices_by_building(db, site.id)
    carbon_values = [float(_building_meta(x).get("annual_emission_tco2e") or 0) for x in buildings]
    items = []
    response_time = _now()
    for building in buildings:
        meta = _building_meta(building); building_devices = devices.get(building.id, [])
        latest_time, latest = _latest_metrics(db, building_devices)
        emission = float(meta["annual_emission_tco2e"]) if meta.get("annual_emission_tco2e") is not None else None
        area = float(building.area_m2 or 0)
        power = latest.get("power_kw") or latest.get("active_power_kw")
        items.append({
            "campus_id": _campus_id(site), "building_id": _building_id(building),
            "floor_id": None, "area_id": None, "timestamp": latest_time or response_time,
            "building_name": building.name, "building_type": building.building_type,
            "current_electricity_kw": power.value if power else None,
            "period_electricity_kwh": meta.get("annual_energy_kwh"),
            "period_water_m3": meta.get("annual_water_m3"),
            "period_hvac_kwh": _metric_sum(db, [d for d in building_devices if d.device_type == "HVAC"], {"energy_kwh", "hvac_energy_kwh"}),
            "period_lighting_kwh": _metric_sum(db, [d for d in building_devices if d.device_type == "LIGHTING"], {"energy_kwh", "lighting_energy_kwh"}),
            "carbon_emission_tco2e": emission,
            "carbon_intensity_kgco2e_m2": emission * 1000 / area if emission is not None and area else None,
            "hotspot_level": _hotspot_level(emission, carbon_values),
            "data_class": meta.get("data_class", DATA_CLASS), "data_notice": meta.get("data_notice", DATA_NOTICE),
        })
    return {"campus_id": _campus_id(site), "timestamp": response_time, "total": len(items), "items": items}


def simulation_results(db: Session, site_id: int) -> dict:
    site = _site(db, site_id)
    task_rows = db.execute(
        select(SimulationTask, Scenario).join(Scenario, Scenario.id == SimulationTask.scenario_id)
        .where(Scenario.enterprise_id == site.enterprise_id, SimulationTask.status == "SUCCESS")
        .order_by(SimulationTask.id.desc())
    ).all()
    seen: set[str] = set(); scenarios = []
    for task, scenario in task_rows:
        key = scenario.scenario_type or scenario.name
        if key in seen:
            continue
        seen.add(key); scenarios.append({"scenario_type": scenario.scenario_type, "scenario_name": scenario.name,
            "task_id": task.id, "scenario_version_id": task.scenario_version_id, "result": task.summary_json})
    runs = list(db.scalars(select(LongTermPathRun).where(LongTermPathRun.enterprise_id == site.enterprise_id,
        LongTermPathRun.status == "SUCCESS").order_by(LongTermPathRun.id.desc())).all())
    strengthened = next((x for x in runs if (x.input_snapshot_json or {}).get("source_run_id")), None)
    original = next((x for x in runs if not (x.input_snapshot_json or {}).get("source_run_id")), runs[0] if runs else None)
    selected = original or strengthened; result = selected.result_snapshot_json if selected else {}
    gap = (result.get("gap_analysis") or {}).get("neutrality_gap_t")
    if gap is None and result:
        gap = result.get("emission_at_end_t")
    return {"campus_id": _campus_id(site), "timestamp": _now(), "scenarios": scenarios,
        "long_term_path": {"run_id": selected.id, "result": result} if selected else None,
        "actual_peak_year": result.get("actual_peak_year"), "actual_neutral_year": result.get("actual_neutral_year"),
        "neutrality_gap_tco2e": gap,
        "strengthened_path": {"run_id": strengthened.id, "source_run_id": strengthened.input_snapshot_json.get("source_run_id"),
            "result": strengthened.result_snapshot_json} if strengthened else None,
        "data_class": (site.metadata_json or {}).get("data_class", DATA_CLASS),
        "data_notice": (site.metadata_json or {}).get("data_notice", DATA_NOTICE)}


def market_results(db: Session, site_id: int, region: str | None = None) -> dict:
    site = _site(db, site_id)
    region = region or (site.metadata_json or {}).get("market_region")
    stmt = select(CarbonMarketTimeseries)
    if region:
        stmt = stmt.where(CarbonMarketTimeseries.region == region)
    rows = list(db.scalars(stmt.order_by(CarbonMarketTimeseries.timestamp)).all())
    latest = rows[-1] if rows else None
    if latest and not region:
        region = latest.region
        rows = [x for x in rows if x.region == region]
        latest = rows[-1]
    assessment = db.scalar(select(CarbonCostAssessment).join(SimulationTask, SimulationTask.id == CarbonCostAssessment.task_id)
        .join(Scenario, Scenario.id == SimulationTask.scenario_id).where(Scenario.enterprise_id == site.enterprise_id)
        .order_by(CarbonCostAssessment.created_at.desc(), CarbonCostAssessment.id.desc()))
    fields = ("carbon_price_per_t", "carbon_quota_t", "trading_volume_t", "ccer_volume_t", "ccer_price_per_t",
              "green_certificate_volume", "green_certificate_price")
    return {"campus_id": _campus_id(site), "timestamp": latest.timestamp if latest else _now(), "region": region,
        "carbon_quota_t": latest.carbon_quota_t if latest else None,
        "carbon_price_yuan_per_t": latest.carbon_price_per_t if latest else None,
        "trading_volume_t": latest.trading_volume_t if latest else None,
        "ccer_volume_t": latest.ccer_volume_t if latest else None, "ccer_price_yuan_per_t": latest.ccer_price_per_t if latest else None,
        "green_certificate_volume": latest.green_certificate_volume if latest else None,
        "green_certificate_price_yuan": latest.green_certificate_price if latest else None,
        "carbon_cost": assessment.result_json if assessment else None,
        "timeseries": [{"timestamp": x.timestamp, "region": x.region, **{field: getattr(x, field) for field in fields}} for x in rows],
        "source": latest.source if latest else None,
        "data_class": (site.metadata_json or {}).get("data_class", DATA_CLASS),
        "data_notice": (site.metadata_json or {}).get("data_notice", DATA_NOTICE)}
