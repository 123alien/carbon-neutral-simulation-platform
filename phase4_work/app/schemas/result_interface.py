from datetime import datetime

from pydantic import Field

from .common import ORMModel


class SpatialReference(ORMModel):
    campus_id: str
    building_id: str | None = None
    floor_id: str | None = None
    area_id: str | None = None
    timestamp: datetime


class CampusOverviewResult(SpatialReference):
    campus_name: str
    annual_electricity_kwh: float | None = None
    annual_water_m3: float | None = None
    annual_natural_gas_m3: float | None = None
    annual_carbon_emission_tco2e: float | None = None
    photovoltaic_generation_kwh: float | None = None
    storage_soc_pct: float | None = None
    building_count: int
    hotspot_buildings: list[dict] = Field(default_factory=list)
    data_class: str
    data_notice: str


class BuildingResult(SpatialReference):
    building_name: str
    building_type: str
    current_electricity_kw: float | None = None
    period_electricity_kwh: float | None = None
    period_water_m3: float | None = None
    period_hvac_kwh: float | None = None
    period_lighting_kwh: float | None = None
    carbon_emission_tco2e: float | None = None
    carbon_intensity_kgco2e_m2: float | None = None
    hotspot_level: str | None = None
    data_class: str
    data_notice: str


class BuildingResultPage(ORMModel):
    campus_id: str
    timestamp: datetime
    total: int
    items: list[BuildingResult]


class SimulationResultInterface(ORMModel):
    campus_id: str
    timestamp: datetime
    scenarios: list[dict] = Field(default_factory=list)
    long_term_path: dict | None = None
    actual_peak_year: int | None = None
    actual_neutral_year: int | None = None
    neutrality_gap_tco2e: float | None = None
    strengthened_path: dict | None = None
    data_class: str
    data_notice: str


class CarbonMarketResultInterface(ORMModel):
    campus_id: str
    timestamp: datetime
    region: str | None = None
    carbon_quota_t: float | None = None
    carbon_price_yuan_per_t: float | None = None
    trading_volume_t: float | None = None
    ccer_volume_t: float | None = None
    ccer_price_yuan_per_t: float | None = None
    green_certificate_volume: float | None = None
    green_certificate_price_yuan: float | None = None
    carbon_cost: dict | None = None
    timeseries: list[dict] = Field(default_factory=list)
    source: str | None = None
    data_class: str
    data_notice: str
