from dataclasses import dataclass, field
from typing import Dict


@dataclass
class SimulationState:
    year: int
    electricity_base_kwh: float
    natural_gas_m3: float = 0.0
    coal_kg: float = 0.0
    oil_kg: float = 0.0
    electricity_after_saving_kwh: float = 0.0
    energy_saved_kwh: float = 0.0
    pv_generation_kwh: float = 0.0
    pv_self_use_kwh: float = 0.0
    pv_export_kwh: float = 0.0
    grid_power_kwh: float = 0.0
    carbon_emission_t: float = 0.0
    investment: float = 0.0
    annual_benefit: float = 0.0
    metadata: Dict[str, float] = field(default_factory=dict)

    def energy_amounts(self) -> dict[str, float]:
        return {
            "electricity": self.grid_power_kwh,
            "natural_gas": self.natural_gas_m3,
            "coal": self.coal_kg,
            "oil": self.oil_kg,
        }


@dataclass
class MeasureResult:
    measure_type: str
    year: int
    energy_saved_kwh: float = 0.0
    generation_kwh: float = 0.0
    investment: float = 0.0
    opex: float = 0.0
    metadata: Dict[str, float] = field(default_factory=dict)


@dataclass
class ScenarioConfig:
    name: str
    start_year: int
    end_year: int
    growth_rates: Dict[str, float] = field(default_factory=dict)
    target_peak_year: int | None = None
    target_neutral_year: int | None = None
    neutrality_epsilon_t: float = 1.0
    peak_stability_years: int = 3
    neutrality_stability_years: int = 3
