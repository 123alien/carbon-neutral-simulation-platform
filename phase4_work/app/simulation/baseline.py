from app.simulation.types import SimulationState


class BaselineEvolution:
    @staticmethod
    def next_year(previous: SimulationState, year: int, growth_rates: dict[str, float]) -> SimulationState:
        def grow(value: float, energy_type: str) -> float:
            return max(value * (1.0 + float(growth_rates.get(energy_type, 0.0))), 0.0)

        return SimulationState(
            year=year,
            electricity_base_kwh=grow(previous.electricity_base_kwh, "electricity"),
            natural_gas_m3=grow(previous.natural_gas_m3, "natural_gas"),
            coal_kg=grow(previous.coal_kg, "coal"),
            oil_kg=grow(previous.oil_kg, "oil"),
        )
