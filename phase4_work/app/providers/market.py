from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import ElectricityPriceTimeseries, GridEmissionFactorTimeseries


@dataclass(frozen=True)
class ElectricityPrice:
    purchase_price_per_kwh: float
    feed_in_tariff_per_kwh: float
    source: str | None = None


class ElectricityPriceProvider(ABC):
    @abstractmethod
    def get_hourly(self, enterprise_id: int, start_utc: datetime, end_utc: datetime) -> dict[datetime, ElectricityPrice]: ...


class DatabaseElectricityPriceProvider(ElectricityPriceProvider):
    def __init__(self, db: Session): self.db = db
    def get_hourly(self, enterprise_id, start_utc, end_utc):
        rows = self.db.scalars(select(ElectricityPriceTimeseries).where(ElectricityPriceTimeseries.enterprise_id == enterprise_id, ElectricityPriceTimeseries.timestamp >= start_utc, ElectricityPriceTimeseries.timestamp < end_utc)).all()
        return {row.timestamp: ElectricityPrice(float(row.purchase_price_per_kwh), float(row.feed_in_tariff_per_kwh), row.source) for row in rows}


class GridEmissionFactorProvider(ABC):
    @abstractmethod
    def get_hourly(self, region: str, start_utc: datetime, end_utc: datetime) -> dict[datetime, float]: ...


class DatabaseGridEmissionFactorProvider(GridEmissionFactorProvider):
    def __init__(self, db: Session): self.db = db
    def get_hourly(self, region, start_utc, end_utc):
        return {timestamp: item["factor"] for timestamp, item in self.get_hourly_details(region, start_utc, end_utc).items()}
    def get_hourly_details(self, region, start_utc, end_utc):
        rows = self.db.scalars(select(GridEmissionFactorTimeseries).where(GridEmissionFactorTimeseries.region.in_([region, "全国", "NATIONAL"]), GridEmissionFactorTimeseries.timestamp >= start_utc, GridEmissionFactorTimeseries.timestamp < end_utc).order_by(GridEmissionFactorTimeseries.timestamp, GridEmissionFactorTimeseries.region == region, GridEmissionFactorTimeseries.id)).all()
        result = {}
        for row in rows:
            if row.timestamp not in result or row.region == region: result[row.timestamp] = {"factor":float(row.factor_kg_per_kwh),"unit":"kgCO2/kWh","source":row.source,"version":row.version,"region":row.region}
        return result
