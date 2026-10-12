from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Enterprise, ElectricityPriceTimeseries, GridEmissionFactorTimeseries
from app.utils.load_import import normalize_timestamp, read_tabular_file


def _parse(db, filename, content, options, kind):
    if kind == "price" and db.get(Enterprise, options.enterprise_id) is None: raise LookupError("enterprise not found")
    _, raw_rows = read_tabular_file(filename, content); parsed=[]; errors=[]; seen={}
    for row_number, raw in enumerate(raw_rows, 2):
        try:
            ts = normalize_timestamp(raw.get(options.mapping.timestamp), options.timezone)
            if ts in seen: raise ValueError(f"timestamp duplicates row {seen[ts]}")
            seen[ts] = row_number
            if kind == "price":
                purchase=float(raw.get(options.mapping.purchase_price)); feed=float(raw.get(options.mapping.feed_in_tariff) or 0) if options.mapping.feed_in_tariff else 0
                if purchase < 0 or feed < 0: raise ValueError("prices must be non-negative")
                parsed.append({"row": row_number, "timestamp": ts, "purchase_price_per_kwh": purchase, "feed_in_tariff_per_kwh": feed})
            else:
                factor=float(raw.get(options.mapping.factor))
                if factor < 0: raise ValueError("factor must be non-negative")
                parsed.append({"row": row_number, "timestamp": ts, "factor_kg_per_kwh": factor})
        except (TypeError, ValueError) as exc: errors.append({"row": row_number, "code": "INVALID_VALUE", "message": str(exc)})
    timestamps=[row["timestamp"] for row in parsed]
    if kind == "price": existing=set(db.scalars(select(ElectricityPriceTimeseries.timestamp).where(ElectricityPriceTimeseries.enterprise_id == options.enterprise_id, ElectricityPriceTimeseries.timestamp.in_(timestamps))).all()) if timestamps else set()
    else: existing=set(db.scalars(select(GridEmissionFactorTimeseries.timestamp).where(GridEmissionFactorTimeseries.region == options.region, GridEmissionFactorTimeseries.version == options.version, GridEmissionFactorTimeseries.timestamp.in_(timestamps))).all()) if timestamps else set()
    for row in parsed:
        if row["timestamp"] in existing: errors.append({"row": row["row"], "code": "ALREADY_EXISTS", "message": "timestamp already exists"})
    invalid={error["row"] for error in errors}; valid=[row for row in parsed if row["row"] not in invalid]
    preview=[{**row, "timestamp": row["timestamp"].replace(tzinfo=timezone.utc)} for row in valid[:options.preview_limit]]
    return {"total_rows": len(raw_rows), "valid_rows": len(valid), "invalid_rows": len(raw_rows)-len(valid), "can_confirm": bool(valid) and not errors, "preview": preview, "errors": errors}, valid


def preview_price(db, filename, content, options): return _parse(db, filename, content, options, "price")
def preview_factor(db, filename, content, options): return _parse(db, filename, content, options, "factor")


def confirm_price(db, filename, content, options):
    report, rows=_parse(db, filename, content, options, "price")
    if not report["can_confirm"]: raise ValueError("file failed validation")
    db.add_all([ElectricityPriceTimeseries(enterprise_id=options.enterprise_id, timestamp=row["timestamp"], purchase_price_per_kwh=row["purchase_price_per_kwh"], feed_in_tariff_per_kwh=row["feed_in_tariff_per_kwh"], source=options.source or filename) for row in rows]); db.commit(); return {"inserted_rows": len(rows)}


def confirm_factor(db, filename, content, options):
    report, rows=_parse(db, filename, content, options, "factor")
    if not report["can_confirm"]: raise ValueError("file failed validation")
    db.add_all([GridEmissionFactorTimeseries(region=options.region, timestamp=row["timestamp"], factor_kg_per_kwh=row["factor_kg_per_kwh"], source=options.source or filename, version=options.version) for row in rows]); db.commit(); return {"inserted_rows": len(rows)}


def query_prices(db, enterprise_id, start, end):
    return list(db.scalars(select(ElectricityPriceTimeseries).where(ElectricityPriceTimeseries.enterprise_id == enterprise_id, ElectricityPriceTimeseries.timestamp >= start, ElectricityPriceTimeseries.timestamp < end).order_by(ElectricityPriceTimeseries.timestamp)).all())


def query_factors(db, region, start, end):
    return list(db.scalars(select(GridEmissionFactorTimeseries).where(GridEmissionFactorTimeseries.region == region, GridEmissionFactorTimeseries.timestamp >= start, GridEmissionFactorTimeseries.timestamp < end).order_by(GridEmissionFactorTimeseries.timestamp)).all())
