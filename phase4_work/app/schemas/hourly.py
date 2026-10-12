from datetime import datetime
from pydantic import Field, model_validator
from .common import ORMModel
from .scenario import ScenarioMeasureCreate


class LoadTimeseriesCreate(ORMModel):
    enterprise_id: int
    timestamp: datetime
    load_kwh: float = Field(ge=0)
    load_kw: float | None = Field(default=None, ge=0)
    irradiation_wm2: float = Field(default=0, ge=0)
    temperature_c: float | None = None
    humidity_pct: float | None = Field(default=None, ge=0, le=100)
    source: str | None = None


class LoadTimeseriesRead(LoadTimeseriesCreate):
    id: int


class LoadImportFieldMapping(ORMModel):
    timestamp: str
    load: str
    irradiation: str | None = None
    temperature: str | None = None
    humidity: str | None = None


class LoadImportOptions(ORMModel):
    enterprise_id: int
    mapping: LoadImportFieldMapping
    load_unit: str = "kW"
    timezone: str = "Asia/Shanghai"
    interval_minutes: int | None = Field(default=None, gt=0, le=1440)
    source: str | None = None
    preview_limit: int = Field(default=20, ge=1, le=200)


class LoadImportError(ORMModel):
    row: int
    field: str | None = None
    code: str
    message: str


class LoadImportPreviewRow(ORMModel):
    row: int
    timestamp_utc: datetime
    load_kw: float
    load_kwh: float
    irradiation_wm2: float = 0
    temperature_c: float | None = None
    humidity_pct: float | None = None


class LoadImportPreviewResponse(ORMModel):
    filename: str
    columns: list[str]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    existing_rows: int
    interval_minutes: int | None
    missing_intervals: int
    can_confirm: bool
    preview: list[LoadImportPreviewRow]
    errors: list[LoadImportError]


class LoadImportConfirmResponse(ORMModel):
    inserted_rows: int
    enterprise_id: int
    interval_minutes: int
    source: str | None = None


class LoadQueryPoint(ORMModel):
    timestamp: datetime
    timestamp_utc: datetime
    load_kw: float
    load_kwh: float
    irradiation_wm2: float = 0
    temperature_c: float | None = None
    humidity_pct: float | None = None
    quality: str = "OBSERVED"


class LoadQueryResponse(ORMModel):
    enterprise_id: int
    timezone: str
    start_utc: datetime
    end_utc: datetime
    count: int
    items: list[LoadQueryPoint]


class LoadAggregateBucket(ORMModel):
    bucket_start: datetime
    bucket_end: datetime
    total_electricity_kwh: float
    peak_load_kw: float | None = None
    average_load_kw: float | None = None
    minimum_load_kw: float | None = None
    peak_valley_difference_kw: float | None = None
    load_factor: float | None = None
    observed_points: int
    expected_points: int
    missing_points: int
    completeness_rate: float
    quality: str


class LoadAggregateResponse(ORMModel):
    enterprise_id: int
    granularity: str
    timezone: str
    interval_minutes: int
    items: list[LoadAggregateBucket]


class LoadStatisticsResponse(ORMModel):
    enterprise_id: int
    timezone: str
    start: datetime
    end: datetime
    total_electricity_kwh: float
    peak_load_kw: float | None = None
    average_load_kw: float | None = None
    minimum_load_kw: float | None = None
    peak_valley_difference_kw: float | None = None
    load_factor: float | None = None
    observed_points: int
    expected_points: int
    missing_points: int
    completeness_rate: float
    quality: str


class MissingInterval(ORMModel):
    start: datetime
    end: datetime
    missing_points: int


class LoadDataQualityResponse(ORMModel):
    enterprise_id: int
    timezone: str
    interval_minutes: int
    observed_points: int
    expected_points: int
    missing_points: int
    duplicate_points: int
    completeness_rate: float
    quality: str
    missing_intervals: list[MissingInterval]


class LoadTimeseriesBulkCreate(ORMModel):
    items: list[LoadTimeseriesCreate]


class HourlySimulationRunRequest(ORMModel):
    site_id: int | None = None
    scenario_id: int
    scenario_version_id: int | None = None
    year: int
    electricity_price_per_kwh: float = Field(default=0.57, ge=0)
    feed_in_tariff_per_kwh: float = Field(default=0.42, ge=0)
    store_hourly_results: bool = True
    temporary_measures: list[ScenarioMeasureCreate] | None = None
    weather_site_id: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_time is not None and self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        return self


class HourlySimulationSummaryRead(ORMModel):
    task_id: int
    scenario_version_id: int | None = None
    scenario_id: int
    year: int
    hours: int
    load_base_kwh: float
    energy_saved_kwh: float
    pv_generation_kwh: float
    pv_self_use_kwh: float
    pv_export_kwh: float
    grid_power_kwh: float
    carbon_emission_t: float
    electricity_cost: float
    feed_in_revenue: float
    pv_self_consumption_rate: float
    pv_load_coverage_rate: float
    storage_charge_kwh: float = 0
    storage_discharge_kwh: float = 0
    curtailed_pv_kwh: float = 0
    ending_storage_soc_kwh: float = 0
    green_power_kwh: float = 0
    green_power_carbon_reduction_t: float = 0
    ev_charging_load_kwh: float = 0
    wind_generation_kwh: float = 0
    wind_self_use_kwh: float = 0
    wind_export_kwh: float = 0
    renewable_generation_kwh: float = 0
    renewable_export_kwh: float = 0
    curtailed_renewable_kwh: float = 0


class HourlyResultRead(ORMModel):
    timestamp: datetime
    load_base_kwh: float
    hvac_saved_kwh: float
    lighting_saved_kwh: float
    load_after_saving_kwh: float
    pv_generation_kwh: float
    pv_self_use_kwh: float
    pv_export_kwh: float
    grid_power_kwh: float
    carbon_emission_t: float
    electricity_cost: float
    feed_in_revenue: float
    storage_charge_kwh: float = 0
    storage_discharge_kwh: float = 0
    storage_soc_kwh: float = 0
    curtailed_pv_kwh: float = 0
    energy_balance_error_kwh: float = 0
    purchase_price_per_kwh: float = 0
    feed_in_tariff_per_kwh: float = 0
    grid_emission_factor_kg_per_kwh: float = 0
    green_power_kwh: float = 0
    green_power_emission_t: float = 0
    green_power_carbon_reduction_t: float = 0
    ev_charging_load_kwh: float = 0
    wind_generation_kwh: float = 0
    wind_self_use_kwh: float = 0
    wind_export_kwh: float = 0
    renewable_generation_kwh: float = 0
    renewable_export_kwh: float = 0
    curtailed_renewable_kwh: float = 0


class HourlySimulationResultRead(ORMModel):
    summary: HourlySimulationSummaryRead
    results: list[HourlyResultRead]
