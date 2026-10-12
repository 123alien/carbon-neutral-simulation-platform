"""Rule-driven demonstration data used only for acceptance and product demos.

The generated values are explicitly synthetic.  They are exposed through REST so
the existing RestApiAdapter, mapping, L1/L2/L3 validation and persistence path are
exercised exactly as they are for an external system.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CarbonAccountingRun, Site
from app.services import localized_data_service

DATA_NOTICE = "示范仿真数据"


def _stamp(value: datetime | None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0)


def _record(device: str, device_type: str, ts: datetime, metric: str, value: float, unit: str) -> dict:
    iso = ts.isoformat().replace("+00:00", "Z")
    return {
        "device_external_id": device,
        "device_name": device,
        "device_type": device_type,
        "timestamp": iso,
        "metric_name": metric,
        "value": round(value, 4),
        "unit": unit,
        "source_record_id": f"{device}:{iso}:{metric}",
        "source": "园区设备采集模拟器",
        "source_status": "正常",
        "quality_flag": "规则校验通过",
        "data_class": "DEMO_SIMULATION",
        "data_notice": DATA_NOTICE,
    }


def telemetry(kind: str, at: datetime | None = None) -> dict:
    ts = _stamp(at); local_hour = (ts.hour + 8) % 24; weekday = ts.weekday() < 5
    phase = ts.timestamp() / 3600
    kind = kind.upper()
    rows: list[dict] = []
    if kind == "WIND":
        speed = max(0.3, 6.6 + 2.1 * math.sin(phase * .37) + .8 * math.sin(phase * .11))
        ratio = 0 if speed < 3 or speed >= 25 else 1 if speed >= 12 else ((speed - 3) / 9) ** 3
        rows = [_record("WIND-AGG-01", "WIND", ts, "wind_speed_m_s", speed, "m/s"), _record("WIND-AGG-01", "WIND", ts, "active_power_kw", 120 * ratio, "kW")]
    elif kind == "EV":
        arrivals = 1.0 if weekday and (7 <= local_hour < 10 or 17 <= local_hour < 20) else .42 if weekday and 10 <= local_hour < 17 else .12
        rows = [_record("EV-AGG-20", "EV_CHARGER", ts, "power_kw", 20 * 7 * .62 * arrivals, "kW"), _record("EV-AGG-20", "EV_CHARGER", ts, "energy_kwh", 20 * 7 * .62 * arrivals / 4, "kWh")]
    elif kind == "STORAGE":
        # A deterministic daily schedule: off-peak charging and evening discharge.
        charge = 36.0 if 1 <= local_hour < 6 else 0.0; discharge = 48.0 if 17 <= local_hour < 21 else 0.0
        charged_hours = max(0, min(local_hour - 1, 5)); discharged_hours = max(0, min(local_hour - 17, 4))
        soc_kwh = min(432.0, max(48.0, 240 + charged_hours * 36 * .95 - discharged_hours * 48 / .95))
        rows = [_record("BESS-01", "STORAGE", ts, "soc_pct", soc_kwh / 480 * 100, "%"), _record("BESS-01", "STORAGE", ts, "power_kw", charge if charge else discharge, "kW"), _record("BESS-01", "STORAGE", ts, "energy_kwh", (charge * .95 if charge else discharge / .95) / 4, "kWh")]
    elif kind == "HVAC":
        outside = 18 + 10 * math.sin(2 * math.pi * (ts.timetuple().tm_yday - 105) / 366) + 4 * math.sin(2 * math.pi * (local_hour - 8) / 24)
        occupied = 1 if weekday and 8 <= local_hour < 19 else .18
        power = (18 + 14 * max(0, outside - 24) + 9 * max(0, 12 - outside)) * occupied
        rows = [_record("HVAC-B01", "HVAC", ts, "temperature_c", outside, "C"), _record("HVAC-B01", "HVAC", ts, "hvac_power_kw", power, "kW")]
    elif kind == "LIGHTING":
        office = 52 if weekday and 8 <= local_hour < 19 else 9 if 6 <= local_hour < 23 else 3
        common = 18 if 6 <= local_hour < 23 else 6
        rows = [_record("LIGHT-AGG", "LIGHTING", ts, "power_kw", office + common, "kW"), _record("LIGHT-AGG", "LIGHTING", ts, "energy_kwh", (office + common) / 4, "kWh")]
    elif kind == "WATER":
        occupied = 1 if weekday and 8 <= local_hour < 19 else .25
        lunch_peak = 1.65 if 11 <= local_hour < 14 else 1
        value = 2.2 * occupied * lunch_peak * (1 + .08 * math.sin(phase * .23))
        rows = [_record("WATER-MAIN-01", "WATER_METER", ts, "water_m3", value / 4, "m3")]
    elif kind == "EMS":
        base = 430 if weekday and 8 <= local_hour < 19 else 190
        power = base * (1 + .08 * math.sin(phase * .19))
        rows = [_record("METER-MAIN", "ELECTRIC_METER", ts, "power_kw", power, "kW"), _record("METER-MAIN", "ELECTRIC_METER", ts, "energy_kwh", power / 4, "kWh")]
    else:
        raise ValueError("unsupported demonstration telemetry type")
    return {"records": rows, "generated_at": ts, "data_class": "DEMO_SIMULATION", "data_notice": DATA_NOTICE}


def standard_validation(site_type: str = "CAMPUS") -> dict:
    items = [
        ("电力", "间接排放", 1_000_000, "千瓦时", .56, "千克二氧化碳当量/千瓦时"),
        ("天然气", "直接排放", 100_000, "立方米", 2.162, "千克二氧化碳/立方米"),
        ("煤", "直接排放", 50_000, "千克", 2.42, "千克二氧化碳/千克"),
        ("燃油", "直接排放", 20_000, "千克", 3.10, "千克二氧化碳/千克"),
        ("外购热力", "间接排放", 300_000, "千瓦时", .11, "千克二氧化碳当量/千瓦时"),
    ]
    mapped=[]
    for energy,scope,activity,unit,factor,factor_unit in items:
        emission=activity*factor/1000
        mapped.append({"energy_type":energy,"boundary":scope,"activity_value":activity,"activity_unit":unit,"factor":factor,"factor_unit":factor_unit,"formula":f"{activity:g} × {factor:g} ÷ 1000","emission_t":emission,"data_class":"DEMO_SIMULATION"})
    normalized=site_type.strip().upper()
    applicability={
        "object_type": normalized,
        "general_standard": "GB/T 32150-2015",
        "industry_series": "GB/T 32151",
        "industry_profile": None,
        "status": "NOT_DIRECTLY_APPLICABLE" if normalized in {"CAMPUS","PUBLIC_INSTITUTION"} else "INDUSTRY_PROFILE_REQUIRED",
        "reason": "湖北经济学院属于校园/公共机构场景，不能在未确定工业行业类别时强行套用GB/T 32151某一分部。" if normalized in {"CAMPUS","PUBLIC_INSTITUTION"} else "需由验收方明确企业所属行业及适用的GB/T 32151现行分部后，再加载行业专属排放源和计算参数。",
        "selection_locked": True,
        "official_catalog": "https://openstd.samr.gov.cn/bzgk/std/std_list?p.p2=32151&p.p90=standard_no&p.p91=asc",
        "review_required": True,
    }
    return {"standard":"GB/T 32150-2015《工业企业温室气体排放核算和报告通则》","claim":"按规范要求实现核算逻辑验证，不代表通过认证；未选定行业时不冒用GB/T 32151分部","boundary":"园区运营控制边界；直接燃料燃烧和外购电力、热力","applicability":applicability,"mapping":mapped,"recalculable_example":mapped[0],"total_emission_t":sum(x["emission_t"] for x in mapped),"data_notice":DATA_NOTICE}


def regional_summary(db: Session, enterprise_id: int) -> dict:
    sites=list(db.scalars(select(Site).where(Site.enterprise_id==enterprise_id).order_by(Site.id)).all())
    rows=[]
    for site in sites:
        result=localized_data_service.carbon(db,site_id=site.id,granularity="month")
        rows.append({"site_id":site.id,"site_name":site.name,"site_type":site.site_type,"total_emission_t":result.get("total_emission_t"),"trend":result.get("trend",[]),"data_status":result.get("data_status")})
    ranked=sorted(rows,key=lambda x:x["total_emission_t"] or -1,reverse=True)
    return {"enterprise_id":enterprise_id,"region_name":"示范区域","data_class":"DEMO_SIMULATION","data_notice":DATA_NOTICE,"site_count":len(rows),"total_emission_t":sum(x["total_emission_t"] or 0 for x in rows),"sites":ranked}
