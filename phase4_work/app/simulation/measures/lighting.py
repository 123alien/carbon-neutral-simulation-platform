from app.simulation.measures.base import MeasureModel
from app.simulation.types import SimulationState, MeasureResult

class LightingSavingModel(MeasureModel):
    measure_type = "LIGHTING"

    def __init__(self, start_year: int, quantity: int, power_before_w: float, power_after_w: float,
                 annual_hours: float, capex: float = 0.0, opex_per_year: float = 0.0,
                 end_year: int | None = None):
        super().__init__(start_year, end_year)
        self.quantity = quantity
        self.power_before_w = power_before_w
        self.power_after_w = power_after_w
        self.annual_hours = annual_hours
        self.capex = capex
        self.opex_per_year = opex_per_year

    def simulate(self, state: SimulationState, year: int) -> MeasureResult:
        if not self.is_active(year):
            return MeasureResult(self.measure_type, year)
        delta_w = max(self.power_before_w - self.power_after_w, 0.0)
        saving = self.quantity * delta_w * self.annual_hours / 1000.0
        # Prevent a measure from saving more electricity than the baseline load.
        saving = min(saving, state.electricity_base_kwh)
        return MeasureResult(self.measure_type, year, energy_saved_kwh=saving,
                             investment=self.capex if year == self.start_year else 0.0,
                             opex=self.opex_per_year)
