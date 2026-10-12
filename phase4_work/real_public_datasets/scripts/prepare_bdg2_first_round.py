"""Prepare the traceable P3-5 first-round REAL_PUBLIC validation files.

Raw inputs are read-only. Missing observations are never filled or interpolated.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
CLEANED = ROOT / "cleaned" / "bdg2_rat_2016"
NORMALIZED = ROOT / "normalized" / "bdg2_rat_2016"
MANIFESTS = ROOT / "manifests"
SELECTED = [
    "Rat_education_Theo",
    "Rat_education_Kathryn",
    "Rat_office_Colby",
    "Rat_office_Avis",
    "Rat_public_Kimber",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def nasa_power() -> pd.DataFrame:
    path = RAW / "weather" / "nasa_power_rat_2016.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    header = next(index for index, line in enumerate(lines) if line.startswith("YEAR,"))
    frame = pd.read_csv(path, skiprows=header)
    frame["timestamp"] = pd.to_datetime(frame[["YEAR", "MO", "DY", "HR"]].rename(columns={"YEAR": "year", "MO": "month", "DY": "day", "HR": "hour"}), utc=True)
    frame = frame.rename(columns={"T2M": "temperature_c", "RH2M": "humidity_pct", "ALLSKY_SFC_SW_DWN": "ghi_w_m2", "WS10M": "wind_speed_m_s", "CLOUD_AMT": "cloud_cover_pct"})
    fields = ["timestamp", "temperature_c", "humidity_pct", "ghi_w_m2", "wind_speed_m_s", "cloud_cover_pct"]
    result = frame[fields].copy()
    result.loc[(result.drop(columns="timestamp") == -999).any(axis=1), fields[1:]] = pd.NA
    return result


def main() -> None:
    CLEANED.mkdir(parents=True, exist_ok=True)
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    repo = RAW / "bdg2" / "source_repo"
    metadata_path = repo / "data" / "metadata" / "metadata.csv"
    electricity_path = repo / "data" / "meters" / "raw" / "electricity.csv"
    weather_path = repo / "data" / "weather" / "weather.csv"

    metadata = pd.read_csv(metadata_path).set_index("building_id")
    selected_meta = metadata.loc[SELECTED].reset_index()
    meter = pd.read_csv(electricity_path, usecols=["timestamp", *SELECTED])
    meter["timestamp"] = pd.to_datetime(meter["timestamp"])
    meter = meter[(meter.timestamp >= "2016-01-01") & (meter.timestamp < "2017-01-01")].copy()

    quality = []
    for building in SELECTED:
        values = meter[building]
        observed = values.notna()
        missing_timestamps = meter.loc[~observed, "timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()
        quality.append({
            "building_id": building,
            "start": meter.timestamp.min().isoformat(),
            "end": meter.timestamp.max().isoformat(),
            "theoretical_points": len(meter),
            "observed_points": int(observed.sum()),
            "completeness_rate": float(observed.mean()),
            "duplicate_timestamps": int(meter.timestamp.duplicated().sum()),
            "missing_points": int((~observed).sum()),
            "missing_timestamps": missing_timestamps,
            "minimum_kwh": float(values.min()),
            "maximum_kwh": float(values.max()),
            "negative_values": int((values.dropna() < 0).sum()),
            "nominal_interval_minutes": 60,
        })

    # Keep every observed fact in the cleaned long-form file; absent rows remain absent.
    long = meter.melt(id_vars="timestamp", value_vars=SELECTED, var_name="building_id", value_name="energy_kwh").dropna()
    long.to_csv(CLEANED / "electricity_observed_long.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")

    all_present = meter[SELECTED].notna().all(axis=1)
    group = (~all_present).cumsum()
    segments = meter.loc[all_present, ["timestamp"]].assign(segment=group[all_present].to_numpy()).groupby("segment").agg(start=("timestamp", "min"), end=("timestamp", "max"), points=("timestamp", "size"))
    chosen = segments.sort_values("points", ascending=False).iloc[0]
    complete = meter[(meter.timestamp >= chosen.start) & (meter.timestamp <= chosen.end)].copy()
    assert complete[SELECTED].notna().all().all()

    # BDG2 electricity is hourly kWh_sum. For a one-hour interval, average kW = kWh / 1 h.
    aggregate = pd.DataFrame({"timestamp": complete.timestamp, "load_kw": complete[SELECTED].sum(axis=1)})
    aggregate.to_csv(NORMALIZED / "hourly_load.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")

    device_rows = long.merge(selected_meta[["building_id", "primaryspaceusage"]], on="building_id", how="left")
    device_rows = device_rows.assign(
        device_external_id=device_rows.building_id + "_electric_meter",
        device_name=device_rows.building_id + " electricity meter",
        device_type="ELECTRIC_METER",
        metric_name="energy_kwh",
        value=device_rows.energy_kwh,
        unit="kWh",
    )[["device_external_id", "device_name", "device_type", "timestamp", "metric_name", "value", "unit"]]
    device_rows.to_csv(NORMALIZED / "device_metrics.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")

    site = pd.DataFrame([{
        "code": "BDG2-RAT",
        "name": "BDG2 Rat Validation Site",
        "site_type": "PUBLIC_INSTITUTION",
        "timezone": "US/Eastern",
        "latitude": float(selected_meta.lat.iloc[0]),
        "longitude": float(selected_meta.lng.iloc[0]),
        "area_m2": float(selected_meta.sqm.sum()),
        "data_class": "REAL_PUBLIC",
        "dataset_id": "BDG2_V1_RAT_2016",
    }])
    site.to_csv(NORMALIZED / "site.csv", index=False)
    buildings = selected_meta[["building_id", "primaryspaceusage", "sub_primaryspaceusage", "sqm", "numberoffloors", "occupants"]].rename(columns={"building_id": "code", "primaryspaceusage": "building_type", "sub_primaryspaceusage": "subtype", "sqm": "area_m2", "numberoffloors": "floor_count", "occupants": "population"})
    buildings["name"] = buildings.code
    buildings["data_class"] = "REAL_PUBLIC"
    buildings["dataset_id"] = "BDG2_V1_RAT_2016"
    buildings.to_csv(NORMALIZED / "buildings.csv", index=False)
    points = pd.DataFrame({
        "code": [f"MP-{name}-ELECTRICITY" for name in SELECTED],
        "name": [f"{name} whole-building electricity" for name in SELECTED],
        "building_code": SELECTED,
        "energy_type": "ELECTRICITY",
        "metric_type": "ENERGY",
        "unit": "kWh",
        "data_class": "REAL_PUBLIC",
        "dataset_id": "BDG2_V1_RAT_2016",
    })
    points.to_csv(NORMALIZED / "metering_points.csv", index=False)

    # NASA POWER is UTC. Slice it to the exact UTC interval represented by the selected local load segment.
    start_utc = chosen.start.tz_localize("US/Eastern").tz_convert("UTC")
    end_utc = (chosen.end + pd.Timedelta(hours=1)).tz_localize("US/Eastern").tz_convert("UTC")
    weather = nasa_power()
    weather_slice = weather[(weather.timestamp >= start_utc) & (weather.timestamp < end_utc)].copy()
    weather_slice["timestamp"] = weather_slice.timestamp.dt.strftime("%Y-%m-%d %H:%M:%S")
    weather_slice.to_csv(NORMALIZED / "weather.csv", index=False)

    # Context files remain at their true period and granularity; they are not applied to the 2017 US site.
    pd.DataFrame([{"timestamp": "2024-01-01 00:00:00", "factor_kg_co2e_per_kwh": 0.5777, "region": "NATIONAL", "version": "MEE-2024-CARBON-FOOTPRINT", "source": "MEE/NBS/NEA Announcement 2025 No.19", "data_class": "REAL_PUBLIC_OFFICIAL"}]).to_csv(NORMALIZED / "china_grid_factor_2024.csv", index=False)
    tou_rows = []
    for season, peak_ratio, valley_ratio in [("NORMAL", 1.8, 0.48), ("SUMMER_WINTER", 2.0, 0.45)]:
        for period, hours, ratio in [("尖峰", "见政策原文", peak_ratio), ("高峰", "见政策原文", 1.49), ("平时", "06:00-12:00;14:00-16:00", 1.0), ("低谷", "00:00-06:00;12:00-14:00", valley_ratio)]:
            tou_rows.append({"effective_from": "2024-05-01", "season": season, "period": period, "hours": hours, "multiplier": ratio, "base_price": "NOT_PROVIDED_BY_POLICY", "data_class": "REAL_PUBLIC_OFFICIAL"})
    pd.DataFrame(tou_rows).to_csv(NORMALIZED / "hubei_tou_policy_2024.csv", index=False)

    quality_path = ROOT / "BDG2_DATA_QUALITY_REPORT.md"
    rows = ["# BDG2 数据质量报告", "", "数据分类：`REAL_PUBLIC`。未补零、未插值、未平移年份。", "", f"选用最长共同完整区间：`{chosen.start}` 至 `{chosen.end}`，共 `{int(chosen.points)}` 个连续小时。", "", "| Building | 观测/理论 | 完整率 | 缺失 | 最小 kWh | 最大 kWh | 负值 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for item in quality:
        rows.append(f"| {item['building_id']} | {item['observed_points']}/{item['theoretical_points']} | {item['completeness_rate']:.4%} | {item['missing_points']} | {item['minimum_kwh']:.4f} | {item['maximum_kwh']:.4f} | {item['negative_values']} |")
    rows += ["", "2016 全年缺失主要位于美国东部夏令时切换小时。平台首轮正式导入使用最长共同连续区间；全年观测事实仍保存在 cleaned/device_metrics 文件中，缺失行没有生成数值。"]
    quality_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    tracked = [metadata_path, electricity_path, weather_path, RAW / "weather" / "nasa_power_rat_2016.csv", RAW / "emission_factor" / "MEE_2024_national_electricity_carbon_footprint_factors.pdf", RAW / "emission_factor" / "EPA_eGRID2016_summary_tables.txt", RAW / "electricity_price" / "Hubei_TOU_policy_2024.html", *sorted(CLEANED.glob("*")), *sorted(NORMALIZED.glob("*"))]
    manifest = {
        "dataset_id": "BDG2_V1_RAT_2016",
        "data_class": "REAL_PUBLIC",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "normalization_script": str(Path(__file__).relative_to(ROOT)),
        "selected_buildings": SELECTED,
        "load_complete_segment": {"start_local": str(chosen.start), "end_local": str(chosen.end), "points": int(chosen.points), "timezone": "US/Eastern"},
        "transformations": ["wide electricity to long observed facts", "hourly kWh_sum divided by one hour to average kW", "aggregate is sum of five observed buildings only within their common complete interval", "NASA POWER subset by corresponding UTC interval"],
        "prohibited_operations_confirmed_absent": ["missing-to-zero", "interpolation", "year shifting", "outlier replacement"],
        "files": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path), "bytes": path.stat().st_size} for path in tracked],
    }
    (MANIFESTS / "bdg2_rat_2016_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
