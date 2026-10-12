from datetime import datetime
from pydantic import Field, model_validator
from .common import ORMModel

class LongTermMeasure(ORMModel):
    measure_type: str
    start_year: int
    end_year: int | None = None
    parameters_json: dict = Field(default_factory=dict)

class LongTermPathRequest(ORMModel):
    site_id:int|None=None
    source_run_id: int | None = None
    scenario_version_id: int
    baseline_task_id: int | None = None
    start_year: int = 2024
    end_year: int = 2060
    target_peak_year: int = 2030
    target_neutral_year: int = 2060
    annual_load_growth_rate: float = 0.01
    comprehensive_energy_target_rate: float | None = None
    carbon_quota_t: float = 2200.0
    annual_quota_change_rate: float = 0.0
    grid_factor_kg_per_kwh: float | None = None
    annual_grid_factor_change_rate: float = -0.015
    electricity_price_per_kwh: float = 0.72
    annual_price_change_rate: float = 0.02
    carbon_price_per_t: float = 85.0
    neutrality_threshold_t: float = 1.0
    measures: list[LongTermMeasure] | None = None

    @model_validator(mode="after")
    def validate_path(self):
        if self.start_year > self.end_year or self.end_year - self.start_year > 100:
            raise ValueError("invalid projection year range")
        if not -0.2 <= self.annual_load_growth_rate <= 0.2:
            raise ValueError("annual_load_growth_rate must be between -0.2 and 0.2")
        if self.neutrality_threshold_t < 0 or self.carbon_quota_t < 0:
            raise ValueError("carbon quota and neutrality threshold cannot be negative")
        return self

class LongTermPathRunRead(ORMModel):
    id: int
    enterprise_id: int
    scenario_version_id: int
    baseline_task_id: int | None
    status: str
    input_snapshot_json: dict
    result_snapshot_json: dict
    created_at: datetime

class StrengthenedPathRequest(ORMModel):
    pv_annual_addition_kw: float = Field(default=0, ge=0)
    wind_annual_addition_kw: float = Field(default=0, ge=0)
    storage_expansion_year: int | None = None
    storage_expansion_kwh: float = Field(default=0, ge=0)
    additional_hvac_saving_rate: float = Field(default=0, ge=0, le=.5)
    additional_lighting_saving_rate: float = Field(default=0, ge=0, le=.5)
    green_power_ratio: float = Field(default=0, ge=0, le=1)
    annual_ccer_t: float = Field(default=0, ge=0)
    annual_grid_factor_change_rate: float | None = Field(default=None, ge=-.2, le=.2)
