"""Prepare a small, auditable ACN-Data static slice without altering observations."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "real_public_datasets"
RAW_REPO = DATA / "raw" / "acn_data" / "ACN-Data-Static"
RAW = RAW_REPO / "time series data" / "caltech" / "California_Garage_01"
CLEANED = DATA / "cleaned" / "acn_data" / "caltech_garage_01_2018_05_01_14"
NORMALIZED = DATA / "normalized" / "acn_data" / "caltech_garage_01_2018_05_01_14"
MANIFEST = DATA / "manifests" / "acn_caltech_2018_05_manifest.json"
STATIONS = ("2-39-129-17", "2-39-138-29", "2-39-139-28")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def main() -> None:
    CLEANED.mkdir(parents=True, exist_ok=True)
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path for path in RAW.glob("*.csv.gz")
        if path.name.startswith(STATIONS) and "2018-05-" in path.name
        and 1 <= int(path.name.split("2018-05-")[1][:2]) <= 14
    )
    sessions = []
    raw_files = []
    for path in files:
        station = next(item for item in STATIONS if path.name.startswith(item + "-"))
        timestamps, currents, energies = [], [], []
        with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                timestamps.append(iso(row[""]))
                current = row.get("Charging Current (A)")
                energy = row.get("Energy Delivered (kWh)")
                currents.append(float(current) if current not in (None, "") else None)
                energies.append(float(energy) if energy not in (None, "") else None)
        if not timestamps:
            continue
        nonzero = [stamp for stamp, current in zip(timestamps, currents) if current is not None and current > 0]
        observed_energy = [value for value in energies if value is not None]
        delivered = max(observed_energy) if observed_energy else None
        sessions.append({
            "session_id": path.name.removesuffix(".csv.gz"),
            "site_id": "caltech",
            "garage_id": "California_Garage_01",
            "station_id": station,
            "connection_time": min(timestamps).isoformat().replace("+00:00", "Z"),
            "disconnect_time": max(timestamps).isoformat().replace("+00:00", "Z"),
            "done_charging_time": (max(nonzero).isoformat().replace("+00:00", "Z") if nonzero else ""),
            "kwh_delivered": delivered,
            "timezone": "America/Los_Angeles",
            "raw_sample_count": len(timestamps),
            "source_file": path.name,
        })
        raw_files.append({"path": str(path.relative_to(DATA)).replace("\\", "/"), "sha256": sha256(path), "bytes": path.stat().st_size})

    sessions.sort(key=lambda row: (row["connection_time"], row["station_id"], row["session_id"]))
    with (CLEANED / "sessions.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(sessions[0])); writer.writeheader(); writer.writerows(sessions)
    devices = [{"external_id": station, "code": station, "name": f"ACN EVSE {station}", "device_type": "EV_CHARGER", "source": "ACN-Data Static"} for station in STATIONS]
    with (NORMALIZED / "devices.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(devices[0])); writer.writeheader(); writer.writerows(devices)
    points = [{"code": f"MP-ACN-{station}", "name": f"{station} session energy", "station_id": station, "metric_type": "energy_kwh", "energy_type": "ELECTRICITY", "unit": "kWh"} for station in STATIONS]
    with (NORMALIZED / "metering_points.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(points[0])); writer.writeheader(); writer.writerows(points)
    metric_fields = ["device_external_id", "device_name", "device_type", "timestamp", "metric_name", "value", "unit", "source_session_id", "connection_time", "done_charging_time", "semantic_granularity", "data_class"]
    with (NORMALIZED / "device_metrics.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=metric_fields); writer.writeheader()
        for session in sessions:
            if session["kwh_delivered"] is None:
                continue
            writer.writerow({"device_external_id": session["station_id"], "device_name": f"ACN EVSE {session['station_id']}", "device_type": "EV_CHARGER", "timestamp": session["disconnect_time"], "metric_name": "energy_kwh", "value": session["kwh_delivered"], "unit": "kWh", "source_session_id": session["session_id"], "connection_time": session["connection_time"], "done_charging_time": session["done_charging_time"], "semantic_granularity": "SESSION_TOTAL_AT_DISCONNECT", "data_class": "REAL_PUBLIC"})
    normalized_files = []
    for path in sorted([CLEANED / "sessions.csv", *NORMALIZED.glob("*.csv")]):
        normalized_files.append({"path": str(path.relative_to(DATA)).replace("\\", "/"), "sha256": sha256(path), "bytes": path.stat().st_size})
    station_counts = {station: sum(row["station_id"] == station for row in sessions) for station in STATIONS}
    quality = {
        "dataset_id": "ACN_DATA_STATIC_CALTECH_2018_05",
        "data_class": "REAL_PUBLIC",
        "source_commit": "abb7cf15cc7108913e965d4375cc7270d532b65f",
        "site": "caltech / California_Garage_01",
        "station_count": len(STATIONS),
        "station_session_counts": station_counts,
        "session_count": len(sessions),
        "time_range": {"start": min(row["connection_time"] for row in sessions), "end": max(row["disconnect_time"] for row in sessions)},
        "timezone": "America/Los_Angeles; raw timestamps UTC",
        "missing_station_id": sum(not row["station_id"] for row in sessions),
        "missing_connection_time": sum(not row["connection_time"] for row in sessions),
        "missing_disconnect_time": sum(not row["disconnect_time"] for row in sessions),
        "missing_kwh_delivered": sum(row["kwh_delivered"] is None for row in sessions),
        "negative_kwh": sum(row["kwh_delivered"] is not None and row["kwh_delivered"] < 0 for row in sessions),
        "disconnect_before_connect": sum(row["disconnect_time"] < row["connection_time"] for row in sessions),
        "duplicate_session_id": len(sessions) - len({row["session_id"] for row in sessions}),
        "raw_sample_count": sum(row["raw_sample_count"] for row in sessions),
        "transformations": ["one static time-series file retained as one session", "session energy is maximum published cumulative Energy Delivered", "session total is timestamped at the actual final observation", "no hourly curve synthesized", "no missing-to-zero, interpolation, value replacement or year shifting"],
        "raw_files": raw_files,
        "outputs": normalized_files,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    MANIFEST.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
