from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Enterprise, WeatherSite, WeatherTimeseries
from app.schemas.weather import WeatherImportOptions, WeatherSiteCreate
from app.utils.load_import import normalize_timestamp, read_tabular_file


def create_site(db: Session, data: WeatherSiteCreate):
    if db.get(Enterprise, data.enterprise_id) is None:
        raise LookupError("enterprise not found")
    try: ZoneInfo(data.timezone)
    except ZoneInfoNotFoundError as exc: raise ValueError(f"unknown timezone: {data.timezone}") from exc
    site = WeatherSite(**data.model_dump())
    db.add(site); db.commit(); db.refresh(site)
    return site


def list_sites(db: Session, enterprise_id: int | None = None):
    stmt=select(WeatherSite)
    if enterprise_id is not None:stmt=stmt.where(WeatherSite.enterprise_id==enterprise_id)
    return list(db.scalars(stmt.order_by(WeatherSite.id)).all())


def _number(raw, name, minimum=None, maximum=None, optional=False):
    if raw is None or str(raw).strip() == "":
        if optional: return None
        raise ValueError(f"{name} is required")
    value = float(raw)
    if minimum is not None and value < minimum: raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum: raise ValueError(f"{name} must be <= {maximum}")
    return value


def parse_weather(db: Session, filename: str, content: bytes, options: WeatherImportOptions):
    site = db.get(WeatherSite, options.site_id)
    if site is None: raise LookupError("weather site not found")
    zone_name = options.timezone or site.timezone
    columns, raw_rows = read_tabular_file(filename, content)
    mapping = options.mapping
    required = [mapping.timestamp, mapping.temperature_c, mapping.humidity_pct, mapping.ghi_w_m2]
    missing = [column for column in required if column not in columns]
    if missing: raise ValueError(f"mapped columns not found: {', '.join(missing)}")
    parsed, errors, seen = [], [], {}
    optional = ["dni_w_m2", "dhi_w_m2", "wind_speed_m_s", "cloud_cover_pct"]
    for number, raw in enumerate(raw_rows, 2):
        try:
            timestamp = normalize_timestamp(raw.get(mapping.timestamp), zone_name)
            if timestamp in seen: raise ValueError(f"timestamp duplicates row {seen[timestamp]}")
            seen[timestamp] = number
            item = {"row": number, "timestamp": timestamp, "temperature_c": _number(raw.get(mapping.temperature_c), "temperature_c"), "humidity_pct": _number(raw.get(mapping.humidity_pct), "humidity_pct", 0, 100), "ghi_w_m2": _number(raw.get(mapping.ghi_w_m2), "ghi_w_m2", 0)}
            for field in optional:
                column = getattr(mapping, field)
                maximum = 100 if field == "cloud_cover_pct" else None
                item[field] = _number(raw.get(column), field, 0, maximum, True) if column else None
            parsed.append(item)
        except (TypeError, ValueError) as exc:
            errors.append({"row": number, "code": "INVALID_VALUE", "message": str(exc)})
    parsed.sort(key=lambda row: row["timestamp"])
    deltas = [int((b["timestamp"] - a["timestamp"]).total_seconds() / 60) for a, b in zip(parsed, parsed[1:])]
    interval = options.interval_minutes or (min((d for d in deltas if d > 0), default=60))
    missing_points = sum(max(delta // interval - 1, 0) for delta in deltas)
    if missing_points: errors.append({"row": 0, "code": "MISSING_INTERVALS", "message": f"{missing_points} expected intervals are missing"})
    timestamps = [row["timestamp"] for row in parsed]
    existing = set(db.scalars(select(WeatherTimeseries.timestamp).where(WeatherTimeseries.site_id == site.id, WeatherTimeseries.timestamp.in_(timestamps))).all()) if timestamps else set()
    for row in parsed:
        if row["timestamp"] in existing: errors.append({"row": row["row"], "code": "ALREADY_EXISTS", "message": "timestamp already exists"})
    invalid = {error["row"] for error in errors if error["row"] > 0}
    valid = [row for row in parsed if row["row"] not in invalid]
    preview = [{**{key: value for key, value in row.items() if key != "timestamp"}, "timestamp_utc": row["timestamp"]} for row in valid[:options.preview_limit]]
    report = {"filename": filename, "columns": columns, "total_rows": len(raw_rows), "valid_rows": len(valid), "invalid_rows": len(raw_rows) - len(valid), "interval_minutes": interval, "missing_points": missing_points, "can_confirm": bool(valid) and not errors, "preview": preview, "errors": errors}
    return report, valid, site


def confirm_weather(db: Session, filename: str, content: bytes, options: WeatherImportOptions):
    report, rows, site = parse_weather(db, filename, content, options)
    if not report["can_confirm"]: raise ValueError("file failed validation")
    db.add_all([WeatherTimeseries(site_id=site.id, timestamp=row["timestamp"], temperature_c=row["temperature_c"], humidity_pct=row["humidity_pct"], ghi_w_m2=row["ghi_w_m2"], dni_w_m2=row["dni_w_m2"], dhi_w_m2=row["dhi_w_m2"], wind_speed_m_s=row["wind_speed_m_s"], cloud_cover_pct=row["cloud_cover_pct"], source=options.source or filename) for row in rows])
    db.commit()
    return {"site_id": site.id, "inserted_rows": len(rows), "interval_minutes": report["interval_minutes"]}


def _range(db, site_id, start, end, timezone_name):
    site = db.get(WeatherSite, site_id)
    if site is None: raise LookupError("weather site not found")
    try: zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc: raise ValueError(f"unknown timezone: {timezone_name}") from exc
    if start.tzinfo is None: start = start.replace(tzinfo=zone)
    if end.tzinfo is None: end = end.replace(tzinfo=zone)
    start_utc, end_utc = start.astimezone(timezone.utc).replace(tzinfo=None), end.astimezone(timezone.utc).replace(tzinfo=None)
    if end_utc <= start_utc: raise ValueError("end must be later than start")
    rows = list(db.scalars(select(WeatherTimeseries).where(WeatherTimeseries.site_id == site_id, WeatherTimeseries.timestamp >= start_utc, WeatherTimeseries.timestamp < end_utc).order_by(WeatherTimeseries.timestamp)).all())
    return zone, start_utc, end_utc, rows


def hourly(db, site_id, start, end, timezone_name):
    zone, _, _, rows = _range(db, site_id, start, end, timezone_name)
    items = [{"timestamp": row.timestamp.replace(tzinfo=timezone.utc).astimezone(zone), "timestamp_utc": row.timestamp.replace(tzinfo=timezone.utc), "temperature_c": row.temperature_c, "humidity_pct": row.humidity_pct, "ghi_w_m2": row.ghi_w_m2, "dni_w_m2": row.dni_w_m2, "dhi_w_m2": row.dhi_w_m2, "wind_speed_m_s": row.wind_speed_m_s, "cloud_cover_pct": row.cloud_cover_pct} for row in rows]
    return {"site_id": site_id, "timezone": timezone_name, "count": len(items), "items": items}


def _quality(rows, start_utc, end_utc, interval):
    expected = int((end_utc - start_utc).total_seconds() // (interval * 60)); observed = len({row.timestamp for row in rows}); missing = max(expected - observed, 0)
    return expected, observed, missing, min(observed / expected, 1) if expected else 0, "COMPLETE" if expected and not missing else ("MISSING" if not observed else "PARTIAL")


def statistics(db, site_id, start, end, timezone_name, interval):
    _, start_utc, end_utc, rows = _range(db, site_id, start, end, timezone_name)
    expected, observed, missing, rate, quality = _quality(rows, start_utc, end_utc, interval)
    temps = [float(row.temperature_c) for row in rows]; humidities = [float(row.humidity_pct) for row in rows]; ghi = [float(row.ghi_w_m2) for row in rows]
    return {"site_id": site_id, "timezone": timezone_name, "average_temperature_c": sum(temps)/len(temps) if temps else None, "minimum_temperature_c": min(temps) if temps else None, "maximum_temperature_c": max(temps) if temps else None, "average_humidity_pct": sum(humidities)/len(humidities) if humidities else None, "peak_ghi_w_m2": max(ghi) if ghi else None, "total_ghi_wh_m2": sum(ghi)*interval/60, "observed_points": observed, "expected_points": expected, "missing_points": missing, "completeness_rate": rate, "quality": quality}


def data_quality(db, site_id, start, end, timezone_name, interval):
    zone, start_utc, end_utc, rows = _range(db, site_id, start, end, timezone_name)
    expected, observed, missing, rate, quality = _quality(rows, start_utc, end_utc, interval)
    existing = {row.timestamp for row in rows}; step = timedelta(minutes=interval); cursor = start_utc; gaps=[]; gap=None; count=0
    while cursor < end_utc:
        if cursor not in existing: gap = gap or cursor; count += 1
        elif gap is not None: gaps.append({"start": gap.replace(tzinfo=timezone.utc).astimezone(zone), "end": cursor.replace(tzinfo=timezone.utc).astimezone(zone), "missing_points": count}); gap=None; count=0
        cursor += step
    if gap is not None: gaps.append({"start": gap.replace(tzinfo=timezone.utc).astimezone(zone), "end": end_utc.replace(tzinfo=timezone.utc).astimezone(zone), "missing_points": count})
    return {"site_id": site_id, "timezone": timezone_name, "interval_minutes": interval, "observed_points": observed, "expected_points": expected, "missing_points": missing, "completeness_rate": rate, "quality": quality, "missing_intervals": gaps}
