from app.simulation.types import SimulationState, MeasureResult

class EconomicEvaluator:
    def __init__(self, electricity_price_per_kwh: float, feed_in_tariff_per_kwh: float = 0.0):
        self.electricity_price = electricity_price_per_kwh
        self.feed_in_tariff = feed_in_tariff_per_kwh

    def evaluate(self, state: SimulationState, results: list[MeasureResult]) -> float:
        saving_benefit = (state.energy_saved_kwh + state.pv_self_use_kwh) * self.electricity_price
        export_benefit = state.pv_export_kwh * self.feed_in_tariff
        opex = sum(r.opex for r in results)
        state.annual_benefit = saving_benefit + export_benefit - opex
        return state.annual_benefit
