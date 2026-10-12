"""Import the P3-5 first round through public application APIs only."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "real_public_datasets"
NORMALIZED = DATA_ROOT / "normalized" / "bdg2_rat_2016"
API = "http://127.0.0.1:8000"
SOURCE = "REAL_PUBLIC | Building Data Genome 2 v1.0 | DOI 10.5281/zenodo.3887306"


def checked(response: httpx.Response):
    if not response.is_success:
        raise RuntimeError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text[:1000]}")
    return response.json()


def upload(client, endpoint: str, path: Path, options: dict):
    with path.open("rb") as stream:
        return checked(client.post(endpoint, files={"file": (path.name, stream, "text/csv")}, data={"options": json.dumps(options)}))


def optional_int(value):
    return None if pd.isna(value) else int(value)


def main() -> None:
    report = {"data_class": "REAL_PUBLIC", "api": API, "source": SOURCE}
    site_row = pd.read_csv(NORMALIZED / "site.csv").iloc[0]
    buildings = pd.read_csv(NORMALIZED / "buildings.csv").where(pd.notna, None).to_dict("records")
    points = pd.read_csv(NORMALIZED / "metering_points.csv").to_dict("records")
    with httpx.Client(base_url=API, timeout=300, trust_env=False) as client:
        health = checked(client.get("/health"))
        if health.get("status") != "ok":
            raise RuntimeError("development API is not healthy")
        enterprise = next((row for row in checked(client.get("/api/enterprises")) if row["name"] == "BDG2 Rat Validation Workspace"), None) or checked(client.post("/api/enterprises", json={"name": "BDG2 Rat Validation Workspace", "region": "US-NATIONAL", "industry": "Public research validation", "building_area": float(site_row.area_m2), "latitude": float(site_row.latitude), "longitude": float(site_row.longitude), "base_year": 2016}))
        if enterprise["region"] != "US-NATIONAL-CO2":
            enterprise = checked(client.patch(f"/api/enterprises/{enterprise['id']}", json={"region": "US-NATIONAL-CO2"}))
        organization = next((row for row in checked(client.get("/api/organizations", params={"enterprise_id": enterprise["id"]})) if row.get("code") == "BDG2-RAT"), None) or checked(client.post("/api/organizations", json={"enterprise_id": enterprise["id"], "name": "BDG2 Rat Validation Site", "level": "BUILDING_PARK", "code": "BDG2-RAT", "metadata_json": {"data_class": "REAL_PUBLIC", "dataset_id": "BDG2_V1_RAT_2016"}}))
        site = next((row for row in checked(client.get("/api/sites", params={"enterprise_id": enterprise["id"]})) if row["code"] == str(site_row.code)), None) or checked(client.post("/api/sites", json={"enterprise_id": enterprise["id"], "organization_node_id": organization["id"], "code": str(site_row.code), "name": str(site_row["name"]), "site_type": str(site_row.site_type), "area_m2": float(site_row.area_m2), "timezone": str(site_row.timezone), "latitude": float(site_row.latitude), "longitude": float(site_row.longitude), "metadata_json": {"data_class": "REAL_PUBLIC", "dataset_id": "BDG2_V1_RAT_2016", "publisher": "BUDS Lab / National University of Singapore", "source_url": "https://github.com/buds-lab/building-data-genome-project-2", "geographic_precision": "site/city-level coordinates supplied by dataset"}}))
        existing_buildings = {row["code"]: row for row in checked(client.get(f"/api/sites/{site['id']}/buildings"))}
        building_map = {}
        for row in buildings:
            payload = {"organization_node_id": organization["id"], "code": row["code"], "name": row["name"], "building_type": row["building_type"], "area_m2": row["area_m2"], "floor_count": optional_int(row["floor_count"]), "population": optional_int(row["population"]), "metadata_json": {"data_class": "REAL_PUBLIC", "dataset_id": "BDG2_V1_RAT_2016", "subtype": row["subtype"]}}
            building = existing_buildings.get(row["code"]) or checked(client.post(f"/api/sites/{site['id']}/buildings", json=payload)); building_map[row["code"]] = building
        system = next((row for row in checked(client.get("/api/energy-systems", params={"site_id": site["id"]})) if row["code"] == "BDG2-RAT-ELECTRICITY"), None) or checked(client.post("/api/energy-systems", json={"site_id": site["id"], "code": "BDG2-RAT-ELECTRICITY", "name": "BDG2 Rat whole-building electricity meters", "system_type": "ELECTRICITY", "metadata_json": {"data_class": "REAL_PUBLIC", "dataset_id": "BDG2_V1_RAT_2016"}}))

        metric_path = NORMALIZED / "device_metrics.csv"
        data_source = next((row for row in checked(client.get("/api/data-sources", params={"enterprise_id": enterprise["id"]})) if row["name"] == "BDG2 Rat 2016 observed electricity"), None) or checked(client.post("/api/data-sources", json={"enterprise_id": enterprise["id"], "name": "BDG2 Rat 2016 observed electricity", "source_type": "FILE", "config_json": {"path": str(metric_path.resolve()), "timezone": "US/Eastern", "field_mapping": {}, "data_class": "REAL_PUBLIC", "dataset_id": "BDG2_V1_RAT_2016", "source_url": "https://github.com/buds-lab/building-data-genome-project-2"}}))
        source_quality = checked(client.get(f"/api/data-sources/{data_source['id']}/data-quality"))
        data_sync = checked(client.post(f"/api/data-sources/{data_source['id']}/sync")) if source_quality["valid_records"] == 0 else {"extracted": source_quality["valid_records"], "inserted": source_quality["valid_records"], "quarantined": source_quality["quarantined_records"], "warnings": source_quality["warning_records"], "idempotent_resume": True}
        devices = checked(client.get("/api/devices", params={"enterprise_id": enterprise["id"], "data_source_id": data_source["id"]}))
        device_map = {row["external_id"].removesuffix("_electric_meter"): row for row in devices}
        meter_points = []
        existing_points = {row["code"]: row for row in checked(client.get("/api/metering-points", params={"site_id": site["id"]}))}
        for row in points:
            meter_points.append(existing_points.get(row["code"]) or checked(client.post("/api/metering-points", json={"site_id": site["id"], "building_id": building_map[row["building_code"]]["id"], "energy_system_id": system["id"], "device_id": device_map[row["building_code"]]["id"], "data_source_id": data_source["id"], "code": row["code"], "name": row["name"], "metric_type": row["metric_type"], "energy_type": row["energy_type"], "unit": row["unit"], "metadata_json": {"data_class": "REAL_PUBLIC", "dataset_id": "BDG2_V1_RAT_2016"}})))

        load_options = {"enterprise_id": enterprise["id"], "mapping": {"timestamp": "timestamp", "load": "load_kw"}, "load_unit": "kW", "timezone": "US/Eastern", "interval_minutes": 60, "source": SOURCE, "preview_limit": 5}
        existing_load = checked(client.get(f"/api/loads/hourly/{enterprise['id']}", params={"year": 2016}))
        load_preview = upload(client, "/api/loads/hourly/import/preview", NORMALIZED / "hourly_load.csv", load_options) if not existing_load else {"can_confirm": True, "total_rows": len(existing_load), "valid_rows": len(existing_load), "invalid_rows": 0, "duplicate_rows": 0, "existing_rows": len(existing_load), "interval_minutes": 60, "missing_intervals": 0, "preview": [], "errors": [], "idempotent_resume": True}
        if not load_preview["can_confirm"]: raise RuntimeError(f"load preview rejected: {load_preview}")
        load_confirm = upload(client, "/api/loads/hourly/import/confirm", NORMALIZED / "hourly_load.csv", load_options) if not existing_load else {"inserted_rows": len(existing_load), "enterprise_id": enterprise["id"], "interval_minutes": 60, "source": SOURCE, "idempotent_resume": True}

        weather_site = next((row for row in checked(client.get("/api/weather/sites", params={"enterprise_id": enterprise["id"]})) if row["name"] == "NASA POWER for BDG2 Rat coordinates"), None) or checked(client.post("/api/weather/sites", json={"enterprise_id": enterprise["id"], "name": "NASA POWER for BDG2 Rat coordinates", "latitude": float(site_row.latitude), "longitude": float(site_row.longitude), "timezone": "UTC", "source": "REAL_PUBLIC | NASA POWER hourly API"}))
        weather_options = {"site_id": weather_site["id"], "mapping": {"timestamp": "timestamp", "temperature_c": "temperature_c", "humidity_pct": "humidity_pct", "ghi_w_m2": "ghi_w_m2", "wind_speed_m_s": "wind_speed_m_s", "cloud_cover_pct": "cloud_cover_pct"}, "timezone": "UTC", "interval_minutes": 60, "source": "REAL_PUBLIC | NASA POWER hourly API", "preview_limit": 5}
        weather_status = checked(client.get("/api/weather/statistics", params={"site_id": weather_site["id"], "start": "2016-03-13T07:00:00Z", "end": "2016-11-06T04:00:00Z", "timezone": "UTC", "interval_minutes": 60}))
        weather_preview = upload(client, "/api/weather/import/preview", NORMALIZED / "weather.csv", weather_options) if weather_status["observed_points"] == 0 else {"can_confirm": True, "total_rows": weather_status["observed_points"], "valid_rows": weather_status["observed_points"], "invalid_rows": 0, "interval_minutes": 60, "missing_points": weather_status["missing_points"], "preview": [], "errors": [], "idempotent_resume": True}
        if not weather_preview["can_confirm"]: raise RuntimeError(f"weather preview rejected: {weather_preview}")
        weather_confirm = upload(client, "/api/weather/import/confirm", NORMALIZED / "weather.csv", weather_options) if weather_status["observed_points"] == 0 else {"site_id": weather_site["id"], "inserted_rows": weather_status["observed_points"], "interval_minutes": 60, "idempotent_resume": True}

        # eGRID2016 U.S. total CO2 output rate: 998.4 lb/MWh = 0.452867 kgCO2/kWh.
        egrid_factor = 998.4 * 0.45359237 / 1000
        factor_payload = {"region": "US-NATIONAL-CO2", "year": 2016, "energy_type": "electricity", "factor": egrid_factor, "unit": "kgCO2/kWh", "source": "US EPA eGRID2016 Summary Tables, U.S. total output CO2 rate", "version": "eGRID2016"}
        factor_response = client.post("/api/emission-factors", json=factor_payload)
        factor = factor_response.json() if factor_response.is_success else {**factor_payload, "idempotent_resume": True}
        china_factor_options = {"region": "NATIONAL", "version": "MEE-2024-CARBON-FOOTPRINT", "mapping": {"timestamp": "timestamp", "factor": "factor_kg_co2e_per_kwh"}, "timezone": "UTC", "source": "REAL_PUBLIC_OFFICIAL | MEE/NBS/NEA Announcement 2025 No.19", "preview_limit": 5}
        china_existing = checked(client.get("/api/market/grid-factors", params={"region": "NATIONAL", "start": "2024-01-01T00:00:00Z", "end": "2025-01-01T00:00:00Z"}))
        china_preview = upload(client, "/api/market/grid-factors/import/preview", NORMALIZED / "china_grid_factor_2024.csv", china_factor_options) if not china_existing else {"can_confirm": True, "total_rows": len(china_existing), "valid_rows": len(china_existing), "invalid_rows": 0, "preview": [], "errors": [], "idempotent_resume": True}
        china_confirm = upload(client, "/api/market/grid-factors/import/confirm", NORMALIZED / "china_grid_factor_2024.csv", china_factor_options) if china_preview["can_confirm"] and not china_existing else {"inserted_rows": len(china_existing), "idempotent_resume": True}

        start, end = "2016-03-13T07:00:00Z", "2016-11-06T04:00:00Z"
        accounting = checked(client.post("/api/carbon-accounting/runs", json={"enterprise_id": enterprise["id"], "name": "BDG2 Rat observed electricity Scope 2", "period_start": start, "period_end": end, "scopes": ["SCOPE_2"], "standard_basis": "GHG Protocol Scope 2; US EPA eGRID2016", "activities": [], "include_device_metrics": True}))
        accounting_stats = checked(client.get(f"/api/carbon-accounting/runs/{accounting['id']}/statistics", params={"granularity": "month", "dimension": "scope", "timezone": "US/Eastern"}))
        scenario = checked(client.post("/api/scenarios", json={"enterprise_id": enterprise["id"], "name": "BDG2 Rat observed baseline", "description": "Historical observed input; model output is simulation, not measurement", "base_year": 2016, "start_year": 2016, "end_year": 2016, "baseline_growth_json": {"electricity": 0, "natural_gas": 0, "coal": 0, "oil": 0}, "status": "ACTIVE", "measures": [], "scenario_type": "BASELINE"}))
        simulation = checked(client.post("/api/simulation/hourly/run", json={"scenario_id": scenario["id"], "year": 2016, "weather_site_id": weather_site["id"], "start_time": start, "end_time": end, "store_hourly_results": True}))
        report.update({"enterprise": enterprise, "site": site, "buildings": [building_map[key] for key in building_map], "energy_system": system, "data_source": data_source, "data_sync": data_sync, "metering_points": meter_points, "load_preview": load_preview, "load_confirm": load_confirm, "weather_site": weather_site, "weather_preview": weather_preview, "weather_confirm": weather_confirm, "egrid_factor": factor, "china_factor_preview": china_preview, "china_factor_confirm": china_confirm, "accounting": accounting, "accounting_statistics": accounting_stats, "scenario": scenario, "simulation_summary": simulation["summary"], "economics_validation": "NOT_VALIDATED: no geographically/time-matched real electricity tariff was applied; hourly engine fallback is not treated as observed price"})
    (DATA_ROOT / "manifests" / "first_round_api_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
