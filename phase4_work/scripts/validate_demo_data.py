"""Read-only validation for the P3-1 synthetic data and rejected import samples."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if os.getenv("ALLOW_SYNTHETIC_VALIDATION") != "1":
    raise RuntimeError("synthetic validation is disabled; set ALLOW_SYNTHETIC_VALIDATION=1 only in an isolated test environment")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./validation_fixture.db")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.main import app

DATA = ROOT / "demo_data"
client = TestClient(app)


def preview(path: str, filename: str, options: dict) -> dict:
    payload = (DATA / "invalid" / filename).read_bytes()
    response = client.post(
        path,
        files={"file": (filename, payload, "text/csv")},
        data={"options": json.dumps(options, ensure_ascii=False)},
    )
    if response.status_code >= 300:
        return {"http_status": response.status_code, "detail": response.text[:500]}
    result = response.json()
    return {
        key: result.get(key)
        for key in (
            "total_rows", "valid_rows", "invalid_rows", "duplicate_rows",
            "existing_rows", "missing_intervals", "missing_points", "can_confirm", "errors",
        )
        if key in result
    }


def get(path: str, params: dict) -> dict:
    response = client.get(path, params=params)
    if response.status_code >= 300:
        raise RuntimeError(f"GET {path}: {response.status_code} {response.text}")
    return response.json()


def main() -> None:
    load_options = {
        "enterprise_id": 1,
        "mapping": {"timestamp": "timestamp", "load": "load_kw"},
        "load_unit": "kW",
        "timezone": "Asia/Shanghai",
        "interval_minutes": 60,
        "source": "SYNTHETIC_DEVELOPMENT_VALIDATION",
    }
    weather_options = {
        "site_id": 1,
        "mapping": {
            "timestamp": "timestamp", "temperature_c": "temperature_c",
            "humidity_pct": "humidity_pct", "ghi_w_m2": "ghi_w_m2",
        },
        "timezone": "Asia/Shanghai",
        "interval_minutes": 60,
        "source": "SYNTHETIC_DEVELOPMENT_VALIDATION",
    }
    invalid = {
        name: preview("/api/loads/hourly/import/preview", name, load_options)
        for name in ("duplicate_timestamp.csv", "missing_interval.csv", "future_timestamp.csv")
    }
    invalid_unit_options = {**load_options, "mapping": {"timestamp": "timestamp", "load": "load"}}
    invalid["invalid_unit.csv"] = preview(
        "/api/loads/hourly/import/preview", "invalid_unit.csv", invalid_unit_options
    )
    invalid["out_of_range.csv"] = preview(
        "/api/weather/import/preview", "out_of_range.csv", weather_options
    )
    time_range = {
        "start": "2024-01-01T00:00:00+08:00",
        "end": "2025-01-01T00:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "interval_minutes": 60,
    }
    quality = {
        "load": get("/api/loads/data-quality", {"enterprise_id": 1, **time_range}),
        "weather": get("/api/weather/data-quality", {"site_id": 1, **time_range}),
        "device_source": get("/api/data-sources/1/data-quality", {}),
    }
    result = {"invalid_previews_only_no_confirm": invalid, "data_quality": quality}
    output = DATA / "validation_result.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
