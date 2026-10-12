from app.simulation.measures.base import MeasureModel
from app.simulation.types import SimulationState, MeasureResult

class PhotovoltaicModel(MeasureModel):
    measure_type = "PV"

    def __init__(self, start_year: int, capacity_kw: float, annual_irradiation_kwh_per_kw: float,
                 system_efficiency: float = 0.85, degradation_rate: float = 0.007,
                 capex: float = 0.0, opex_per_year: float = 0.0, end_year: int | None = None):
        super().__init__(start_year, end_year)
        self.capacity_kw = capacity_kw
        self.annual_irradiation_kwh_per_kw = annual_irradiation_kwh_per_kw
        self.system_efficiency = system_efficiency
        self.degradation_rate = degradation_rate
        self.capex = capex
        self.opex_per_year = opex_per_year

    def simulate(self, state: SimulationState, year: int) -> MeasureResult:
        if not self.is_active(year):
            return MeasureResult(self.measure_type, year)
        age = year - self.start_year
        generation = (self.capacity_kw * self.annual_irradiation_kwh_per_kw *
                      self.system_efficiency * ((1 - self.degradation_rate) ** age))
        return MeasureResult(
            measure_type=self.measure_type,
            year=year,
            generation_kwh=max(generation, 0.0),
            investment=self.capex if year == self.start_year else 0.0,
            opex=self.opex_per_year,
        )
