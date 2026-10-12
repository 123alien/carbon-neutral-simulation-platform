from datetime import datetime
from pydantic import Field
from .common import ORMModel


class WeatherSiteCreate(ORMModel):
    enterprise_id: int
    name: str = Field(min_length=1, max_length=200)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str = "UTC"
    source: str | None = None


class WeatherSiteRead(WeatherSiteCreate):
    id: int
    created_at: datetime


class WeatherFieldMapping(ORMModel):
    timestamp: str
    temperature_c: str
    humidity_pct: str
    ghi_w_m2: str
    dni_w_m2: str | None = None
    dhi_w_m2: str | None = None
    wind_speed_m_s: str | None = None
    cloud_cover_pct: str | None = None


class WeatherImportOptions(ORMModel):
    site_id: int
    mapping: WeatherFieldMapping
    timezone: str | None = None
    interval_minutes: int | None = Field(default=None, gt=0, le=1440)
    source: str | None = None
    preview_limit: int = Field(default=20, ge=1, le=200)


class WeatherPoint(ORMModel):
    timestamp: datetime
    timestamp_utc: datetime
    temperature_c: float
    humidity_pct: float
    ghi_w_m2: float
    dni_w_m2: float | None = None
    dhi_w_m2: float | None = None
    wind_speed_m_s: float | None = None
    cloud_cover_pct: float | None = None


class WeatherImportPreview(ORMModel):
    filename: str
    columns: list[str]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    interval_minutes: int
    missing_points: int
    can_confirm: bool
    preview: list[dict]
    errors: list[dict]


class WeatherImportConfirm(ORMModel):
    site_id: int
    inserted_rows: int
    interval_minutes: int


class WeatherHourlyResponse(ORMModel):
    site_id: int
    timezone: str
    count: int
    items: list[WeatherPoint]


class WeatherStatistics(ORMModel):
    site_id: int
    timezone: str
    average_temperature_c: float | None = None
    minimum_temperature_c: float | None = None
    maximum_temperature_c: float | None = None
    average_humidity_pct: float | None = None
    peak_ghi_w_m2: float | None = None
    total_ghi_wh_m2: float
    observed_points: int
    expected_points: int
    missing_points: int
    completeness_rate: float
    quality: str


class WeatherDataQuality(ORMModel):
    site_id: int
    timezone: str
    interval_minutes: int
    observed_points: int
    expected_points: int
    missing_points: int
    completeness_rate: float
    quality: str
    missing_intervals: list[dict]
