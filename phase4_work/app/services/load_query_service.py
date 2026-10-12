from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Enterprise, LoadTimeseries


GRANULARITIES = {"hour", "day", "month", "year"}


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {name}") from exc


def _as_utc_naive(value: datetime, zone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=zone)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _validate(db: Session, enterprise_id: int, start: datetime, end: datetime, timezone_name: str):
    if db.get(Enterprise, enterprise_id) is None:
        raise LookupError("enterprise not found")
    zone = _zone(timezone_name)
    start_utc, end_utc = _as_utc_naive(start, zone), _as_utc_naive(end, zone)
    if end_utc <= start_utc:
        raise ValueError("end must be later than start")
    return zone, start_utc, end_utc


def _rows(db: Session, enterprise_id: int, start_utc: datetime, end_utc: datetime):
    return list(db.scalars(select(LoadTimeseries).where(
        LoadTimeseries.enterprise_id == enterprise_id,
        LoadTimeseries.timestamp >= start_utc,
        LoadTimeseries.timestamp < end_utc,
    ).order_by(LoadTimeseries.timestamp)).all())


def _load_kw(row: LoadTimeseries) -> float:
    return float(row.load_kw if row.load_kw is not None else row.load_kwh)


def _quality(observed: int, expected: int) -> tuple[int, float, str]:
    missing = max(expected - observed, 0)
    completeness = min(observed / expected, 1.0) if expected else 0.0
    status = "COMPLETE" if expected and missing == 0 else ("MISSING" if observed == 0 else "PARTIAL")
    return missing, completeness, status


def _metrics(rows, expected: int):
    loads = [_load_kw(row) for row in rows]
    total = sum(float(row.load_kwh) for row in rows)
    peak = max(loads) if loads else None
    average = sum(loads) / len(loads) if loads else None
    minimum = min(loads) if loads else None
    missing, completeness, quality = _quality(len(rows), expected)
    return {"total_electricity_kwh": total, "peak_load_kw": peak, "average_load_kw": average, "minimum_load_kw": minimum, "peak_valley_difference_kw": peak - minimum if peak is not None else None, "load_factor": average / peak if peak and average is not None else None, "observed_points": len(rows), "expected_points": expected, "missing_points": missing, "completeness_rate": completeness, "quality": quality}


def query_loads(db: Session, enterprise_id: int, start: datetime, end: datetime, timezone_name: str):
    zone, start_utc, end_utc = _validate(db, enterprise_id, start, end, timezone_name)
    rows = _rows(db, enterprise_id, start_utc, end_utc)
    items = [{"timestamp": row.timestamp.replace(tzinfo=timezone.utc).astimezone(zone), "timestamp_utc": row.timestamp.replace(tzinfo=timezone.utc), "load_kw": _load_kw(row), "load_kwh": float(row.load_kwh), "irradiation_wm2": float(row.irradiation_wm2 or 0), "temperature_c": row.temperature_c, "humidity_pct": row.humidity_pct, "quality": "OBSERVED"} for row in rows]
    return {"enterprise_id": enterprise_id, "timezone": timezone_name, "start_utc": start_utc.replace(tzinfo=timezone.utc), "end_utc": end_utc.replace(tzinfo=timezone.utc), "count": len(items), "items": items}


def _floor(value: datetime, granularity: str) -> datetime:
    if granularity == "hour": return value.replace(minute=0, second=0, microsecond=0)
    if granularity == "day": return value.replace(hour=0, minute=0, second=0, microsecond=0)
    if granularity == "month": return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _next(value: datetime, granularity: str) -> datetime:
    if granularity == "hour": return value + timedelta(hours=1)
    if granularity == "day": return value + timedelta(days=1)
    if granularity == "month": return value.replace(year=value.year + (value.month == 12), month=1 if value.month == 12 else value.month + 1)
    return value.replace(year=value.year + 1)


def aggregate_loads(db: Session, enterprise_id: int, start: datetime, end: datetime, timezone_name: str, granularity: str, interval_minutes: int):
    if granularity not in GRANULARITIES:
        raise ValueError("granularity must be hour, day, month or year")
    zone, start_utc, end_utc = _validate(db, enterprise_id, start, end, timezone_name)
    rows = _rows(db, enterprise_id, start_utc, end_utc)
    grouped = defaultdict(list)
    for row in rows:
        local = row.timestamp.replace(tzinfo=timezone.utc).astimezone(zone)
        grouped[_floor(local, granularity)].append(row)
    cursor = _floor(start_utc.replace(tzinfo=timezone.utc).astimezone(zone), granularity)
    local_end = end_utc.replace(tzinfo=timezone.utc).astimezone(zone)
    items = []
    while cursor < local_end:
        following = _next(cursor, granularity)
        clipped_start = max(cursor.astimezone(timezone.utc), start_utc.replace(tzinfo=timezone.utc))
        clipped_end = min(following.astimezone(timezone.utc), end_utc.replace(tzinfo=timezone.utc))
        expected = max(int((clipped_end - clipped_start).total_seconds() // (interval_minutes * 60)), 0)
        items.append({"bucket_start": cursor, "bucket_end": following, **_metrics(grouped.get(cursor, []), expected)})
        cursor = following
    return {"enterprise_id": enterprise_id, "granularity": granularity, "timezone": timezone_name, "interval_minutes": interval_minutes, "items": items}


def statistics(db: Session, enterprise_id: int, start: datetime, end: datetime, timezone_name: str, interval_minutes: int):
    zone, start_utc, end_utc = _validate(db, enterprise_id, start, end, timezone_name)
    rows = _rows(db, enterprise_id, start_utc, end_utc)
    expected = int((end_utc - start_utc).total_seconds() // (interval_minutes * 60))
    return {"enterprise_id": enterprise_id, "timezone": timezone_name, "start": start_utc.replace(tzinfo=timezone.utc).astimezone(zone), "end": end_utc.replace(tzinfo=timezone.utc).astimezone(zone), **_metrics(rows, expected)}


def data_quality(db: Session, enterprise_id: int, start: datetime, end: datetime, timezone_name: str, interval_minutes: int):
    zone, start_utc, end_utc = _validate(db, enterprise_id, start, end, timezone_name)
    rows = _rows(db, enterprise_id, start_utc, end_utc)
    expected = int((end_utc - start_utc).total_seconds() // (interval_minutes * 60))
    timestamps = [row.timestamp for row in rows]
    timestamp_set = set(timestamps)
    missing_ranges = []
    cursor = start_utc
    gap_start = None
    gap_count = 0
    step = timedelta(minutes=interval_minutes)
    while cursor < end_utc:
        if cursor not in timestamp_set:
            gap_start = gap_start or cursor
            gap_count += 1
        elif gap_start is not None:
            missing_ranges.append({"start": gap_start.replace(tzinfo=timezone.utc).astimezone(zone), "end": cursor.replace(tzinfo=timezone.utc).astimezone(zone), "missing_points": gap_count})
            gap_start, gap_count = None, 0
        cursor += step
    if gap_start is not None:
        missing_ranges.append({"start": gap_start.replace(tzinfo=timezone.utc).astimezone(zone), "end": end_utc.replace(tzinfo=timezone.utc).astimezone(zone), "missing_points": gap_count})
    missing, completeness, quality = _quality(len(timestamp_set), expected)
    return {"enterprise_id": enterprise_id, "timezone": timezone_name, "interval_minutes": interval_minutes, "observed_points": len(timestamp_set), "expected_points": expected, "missing_points": missing, "duplicate_points": len(timestamps) - len(timestamp_set), "completeness_rate": completeness, "quality": quality, "missing_intervals": missing_ranges}
