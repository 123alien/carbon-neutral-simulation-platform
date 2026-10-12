from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WeatherSite, WeatherTimeseries


@dataclass(frozen=True)
class WeatherObservation:
    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    ghi_w_m2: float
    dni_w_m2: float | None = None
    dhi_w_m2: float | None = None
    wind_speed_m_s: float | None = None
    cloud_cover_pct: float | None = None
    source: str | None = None


class WeatherProvider(ABC):
    @abstractmethod
    def get_hourly(self, enterprise_id: int, start_utc: datetime, end_utc: datetime) -> list[WeatherObservation]:
        """Return UTC-naive observations for the requested half-open range."""


class DatabaseWeatherProvider(WeatherProvider):
    def __init__(self, db: Session, preferred_site_id: int | None = None):
        self.db = db
        self.site_id: int | None = None
        self.preferred_site_id = preferred_site_id

    def get_hourly(self, enterprise_id: int, start_utc: datetime, end_utc: datetime) -> list[WeatherObservation]:
        stmt=select(WeatherSite).where(WeatherSite.enterprise_id == enterprise_id)
        if self.preferred_site_id is not None:stmt=stmt.where(WeatherSite.id==self.preferred_site_id)
        site = self.db.scalars(stmt.order_by(WeatherSite.id)).first()
        if site is None:
            return []
        self.site_id = site.id
        rows = self.db.scalars(select(WeatherTimeseries).where(WeatherTimeseries.site_id == site.id, WeatherTimeseries.timestamp >= start_utc, WeatherTimeseries.timestamp < end_utc).order_by(WeatherTimeseries.timestamp)).all()
        return [WeatherObservation(timestamp=row.timestamp, temperature_c=float(row.temperature_c), humidity_pct=float(row.humidity_pct), ghi_w_m2=float(row.ghi_w_m2), dni_w_m2=row.dni_w_m2, dhi_w_m2=row.dhi_w_m2, wind_speed_m_s=row.wind_speed_m_s, cloud_cover_pct=row.cloud_cover_pct, source=row.source or site.source) for row in rows]
