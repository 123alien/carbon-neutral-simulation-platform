from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import EnergyHistory, EmissionFactor
from app.schemas.energy import EnergyHistoryCreate, EmissionFactorCreate
from app.simulation.unit_conversion import UnitConverter
from app.simulation.growth import GrowthEstimator


def add_energy(db: Session, data: EnergyHistoryCreate) -> EnergyHistory:
    # Fail early if unit/type cannot be normalized by the simulation engine.
    UnitConverter.convert(data.energy_type, data.consumption, data.unit)
    obj = EnergyHistory(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


def list_energy(db: Session, enterprise_id: int, year: int | None = None) -> list[EnergyHistory]:
    stmt = select(EnergyHistory).where(EnergyHistory.enterprise_id == enterprise_id)
    if year is not None:
        stmt = stmt.where(EnergyHistory.year == year)
    return list(db.scalars(stmt.order_by(EnergyHistory.year, EnergyHistory.month)).all())


def add_emission_factor(db: Session, data: EmissionFactorCreate) -> EmissionFactor:
    obj = EmissionFactor(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


def resolve_emission_factor(db: Session, region: str | None, year: int, energy_type: str) -> EmissionFactor | None:
    """Use the newest factor not later than simulation year; region first, national fallback."""
    regions = [region, "全国", "NATIONAL"] if region else ["全国", "NATIONAL"]
    for r in regions:
        if not r:
            continue
        stmt = (select(EmissionFactor)
                .where(EmissionFactor.region == r, EmissionFactor.energy_type == energy_type,
                       EmissionFactor.year <= year)
                .order_by(EmissionFactor.year.desc(), EmissionFactor.id.desc()))
        obj = db.scalars(stmt).first()
        if obj:
            return obj
    stmt = (select(EmissionFactor)
            .where(EmissionFactor.energy_type == energy_type, EmissionFactor.year <= year)
            .order_by(EmissionFactor.year.desc(), EmissionFactor.id.desc()))
    obj = db.scalars(stmt).first()
    if obj:
        return obj
    # If only future factors exist, use the nearest available as explicit last resort.
    stmt = (select(EmissionFactor).where(EmissionFactor.energy_type == energy_type)
            .order_by(EmissionFactor.year.asc(), EmissionFactor.id.desc()))
    return db.scalars(stmt).first()


def annual_energy_totals(db: Session, enterprise_id: int, energy_type: str) -> list[tuple[int, float]]:
    rows = list(db.scalars(select(EnergyHistory).where(
        EnergyHistory.enterprise_id == enterprise_id,
        EnergyHistory.energy_type == energy_type,
    )).all())
    by_year: dict[int, list[EnergyHistory]] = defaultdict(list)
    for r in rows:
        by_year[r.year].append(r)

    totals: list[tuple[int, float]] = []
    for year, year_rows in by_year.items():
        annual = [r for r in year_rows if r.month is None]
        selected = annual if annual else year_rows
        total = 0.0
        for r in selected:
            total += UnitConverter.convert(energy_type, float(r.consumption), r.unit).value
        totals.append((year, total))
    return sorted(totals)


def estimate_growth(db: Session, enterprise_id: int, energy_type: str, method: str = "median_yoy") -> dict:
    values = annual_energy_totals(db, enterprise_id, energy_type)
    if method == "cagr":
        rate = GrowthEstimator.cagr(values)
    elif method == "median_yoy":
        rate = GrowthEstimator.robust_rate(values)
    else:
        raise ValueError("method must be median_yoy or cagr")
    return {
        "enterprise_id": enterprise_id,
        "energy_type": energy_type,
        "method": method,
        "rate": rate,
        "years_used": [y for y, _ in values],
        "canonical_unit": UnitConverter.canonical_unit(energy_type),
    }


def add_load_points(db: Session, items: list):
    from app.models import LoadTimeseries
    objs = []
    for data in items:
        values = data.model_dump()
        if values.get("load_kw") is None:
            values["load_kw"] = values["load_kwh"]
        obj = LoadTimeseries(**values)
        db.add(obj)
        objs.append(obj)
    db.commit()
    for obj in objs:
        db.refresh(obj)
    return objs


def list_load_points(db: Session, enterprise_id: int, year: int | None = None):
    from app.models import LoadTimeseries
    stmt = select(LoadTimeseries).where(LoadTimeseries.enterprise_id == enterprise_id)
    if year is not None:
        from datetime import datetime
        stmt = stmt.where(
            LoadTimeseries.timestamp >= datetime(year, 1, 1),
            LoadTimeseries.timestamp < datetime(year + 1, 1, 1),
        )
    return list(db.scalars(stmt.order_by(LoadTimeseries.timestamp)).all())
