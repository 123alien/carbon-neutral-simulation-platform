from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Enterprise, LoadTimeseries
from app.schemas.hourly import LoadImportOptions
from app.utils.load_import import convert_power_to_kw, normalize_timestamp, read_tabular_file


@dataclass
class ParsedImport:
    report: dict
    rows: list[dict]


def _optional_float(raw, field: str, minimum: float | None = None, maximum: float | None = None):
    if raw is None or str(raw).strip() == "":
        return None
    value = float(raw)
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{field} must be <= {maximum}")
    return value


def parse_and_validate(db: Session, filename: str, content: bytes, options: LoadImportOptions) -> ParsedImport:
    if db.get(Enterprise, options.enterprise_id) is None:
        raise LookupError("enterprise not found")
    columns, raw_rows = read_tabular_file(filename, content)
    required = {options.mapping.timestamp, options.mapping.load}
    missing_columns = sorted(name for name in required if name not in columns)
    if missing_columns:
        raise ValueError(f"mapped columns not found: {', '.join(missing_columns)}")

    errors: list[dict] = []
    parsed: list[dict] = []
    seen: dict = {}
    duplicate_rows = 0
    for row_number, raw in enumerate(raw_rows, start=2):
        try:
            timestamp = normalize_timestamp(raw.get(options.mapping.timestamp), options.timezone)
            if timestamp > datetime.utcnow():
                raise ValueError("timestamp cannot be in the future")
            load_kw = convert_power_to_kw(raw.get(options.mapping.load), options.load_unit)
            irradiation = _optional_float(raw.get(options.mapping.irradiation), "irradiation", 0) if options.mapping.irradiation else 0.0
            temperature = _optional_float(raw.get(options.mapping.temperature), "temperature") if options.mapping.temperature else None
            humidity = _optional_float(raw.get(options.mapping.humidity), "humidity", 0, 100) if options.mapping.humidity else None
            if timestamp in seen:
                duplicate_rows += 1
                errors.append({"row": row_number, "field": options.mapping.timestamp, "code": "DUPLICATE_IN_FILE", "message": f"duplicates row {seen[timestamp]}"})
                continue
            seen[timestamp] = row_number
            parsed.append({"row": row_number, "timestamp": timestamp, "load_kw": load_kw, "irradiation_wm2": irradiation or 0.0, "temperature_c": temperature, "humidity_pct": humidity})
        except (TypeError, ValueError) as exc:
            errors.append({"row": row_number, "field": None, "code": "INVALID_VALUE", "message": str(exc)})

    parsed.sort(key=lambda item: item["timestamp"])
    intervals = [int((b["timestamp"] - a["timestamp"]).total_seconds() / 60) for a, b in zip(parsed, parsed[1:]) if b["timestamp"] > a["timestamp"]]
    interval = options.interval_minutes or (min(intervals) if intervals else 60)
    missing_intervals = sum(max(delta // interval - 1, 0) for delta in intervals)
    if missing_intervals:
        errors.append({"row": 0, "field": "timestamp", "code": "MISSING_INTERVALS", "message": f"{missing_intervals} expected intervals are missing"})
    if any(delta % interval for delta in intervals):
        errors.append({"row": 0, "field": "timestamp", "code": "IRREGULAR_INTERVAL", "message": f"timestamps are not aligned to {interval}-minute intervals"})

    timestamps = [item["timestamp"] for item in parsed]
    existing = set()
    if timestamps:
        existing = set(db.scalars(select(LoadTimeseries.timestamp).where(LoadTimeseries.enterprise_id == options.enterprise_id, LoadTimeseries.timestamp.in_(timestamps))).all())
    for item in parsed:
        item["load_kwh"] = item["load_kw"] * interval / 60
        if item["timestamp"] in existing:
            errors.append({"row": item["row"], "field": "timestamp", "code": "ALREADY_EXISTS", "message": "timestamp already exists for enterprise"})

    invalid_row_numbers = {error["row"] for error in errors if error["row"] > 0}
    valid_rows = [item for item in parsed if item["row"] not in invalid_row_numbers]
    preview = [{"row": item["row"], "timestamp_utc": item["timestamp"], "load_kw": item["load_kw"], "load_kwh": item["load_kwh"], "irradiation_wm2": item["irradiation_wm2"], "temperature_c": item["temperature_c"], "humidity_pct": item["humidity_pct"]} for item in valid_rows[:options.preview_limit]]
    report = {"filename": filename, "columns": columns, "total_rows": len(raw_rows), "valid_rows": len(valid_rows), "invalid_rows": len(raw_rows) - len(valid_rows), "duplicate_rows": duplicate_rows, "existing_rows": len(existing), "interval_minutes": interval, "missing_intervals": missing_intervals, "can_confirm": bool(valid_rows) and not errors and missing_intervals == 0, "preview": preview, "errors": errors}
    return ParsedImport(report=report, rows=valid_rows)


def confirm_import(db: Session, filename: str, content: bytes, options: LoadImportOptions) -> dict:
    result = parse_and_validate(db, filename, content, options)
    if not result.report["can_confirm"]:
        raise ValueError("file failed validation; preview the file and resolve all errors before confirmation")
    interval = result.report["interval_minutes"]
    objects = [LoadTimeseries(enterprise_id=options.enterprise_id, timestamp=row["timestamp"], load_kw=row["load_kw"], load_kwh=row["load_kwh"], irradiation_wm2=row["irradiation_wm2"], temperature_c=row["temperature_c"], humidity_pct=row["humidity_pct"], source=options.source or filename) for row in result.rows]
    db.add_all(objects)
    db.commit()
    return {"inserted_rows": len(objects), "enterprise_id": options.enterprise_id, "interval_minutes": interval, "source": options.source or filename}
