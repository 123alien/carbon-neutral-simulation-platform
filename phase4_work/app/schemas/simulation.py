from datetime import datetime
from .common import ORMModel

class SimulationRunRequest(ORMModel):
    site_id:int|None=None
    scenario_id: int
    scenario_version_id: int | None = None
    electricity_price_per_kwh: float = 0.57
    feed_in_tariff_per_kwh: float = 0.42
    neutrality_epsilon_t: float = 1.0
    peak_stability_years: int = 3
    neutrality_stability_years: int = 3

class SimulationYearResultRead(ORMModel):
    year: int
    electricity_base_kwh: float
    electricity_after_saving_kwh: float
    grid_power_kwh: float
    natural_gas_m3: float
    coal_kg: float
    oil_kg: float
    pv_generation_kwh: float
    pv_self_use_kwh: float
    pv_export_kwh: float
    energy_saved_kwh: float
    carbon_emission_t: float
    carbon_reduction_t: float
    investment: float
    annual_benefit: float

class SimulationTaskRead(ORMModel):
    id: int
    scenario_id: int
    status: str
    summary_json: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None

class SimulationResultRead(ORMModel):
    task: SimulationTaskRead
    results: list[SimulationYearResultRead]


class MultiScenarioCompareRequest(ORMModel):
    scenario_ids: list[int]
    electricity_price_per_kwh: float = 0.57
    feed_in_tariff_per_kwh: float = 0.42
    neutrality_epsilon_t: float = 1.0
    peak_stability_years: int = 3
    neutrality_stability_years: int = 3

class ScenarioCompareItem(ORMModel):
    scenario_id: int
    task_id: int
    name: str
    peak_year: int | None
    neutral_year: int | None
    cumulative_emission_t: float
    cumulative_investment: float
    cumulative_benefit: float

class MultiScenarioCompareRead(ORMModel):
    items: list[ScenarioCompareItem]
