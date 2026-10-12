from app.simulation.measures.base import MeasureModel
from app.simulation.types import SimulationState, MeasureResult

class HVACSavingModel(MeasureModel):
    measure_type = "HVAC"

    def __init__(self, start_year: int, load_share: float, saving_rate: float,
                 capex: float = 0.0, opex_per_year: float = 0.0, end_year: int | None = None):
        super().__init__(start_year, end_year)
        self.load_share = load_share
        self.saving_rate = saving_rate
        self.capex = capex
        self.opex_per_year = opex_per_year

    def simulate(self, state: SimulationState, year: int) -> MeasureResult:
        if not self.is_active(year):
            return MeasureResult(self.measure_type, year)
        saving = state.electricity_base_kwh * self.load_share * self.saving_rate
        return MeasureResult(self.measure_type, year, energy_saved_kwh=max(saving, 0.0),
                             investment=self.capex if year == self.start_year else 0.0,
                             opex=self.opex_per_year)
