from dataclasses import dataclass
from collections.abc import Callable
from app.simulation.types import SimulationState, ScenarioConfig
from app.simulation.baseline import BaselineEvolution
from app.simulation.balance import EnergyBalance
from app.simulation.carbon import CarbonAccounting
from app.simulation.economics import EconomicEvaluator
from app.simulation.detectors import PeakDetector, NeutralityDetector


@dataclass
class ScenarioSummary:
    name: str
    peak_year: int | None
    neutral_year: int | None
    cumulative_emission_t: float
    cumulative_investment: float
    cumulative_benefit: float
    states: list[SimulationState]


class SimulationOrchestrator:
    def __init__(self, factor_provider: Callable[[int], dict[str, float]], economics: EconomicEvaluator):
        self.factor_provider = factor_provider
        self.economics = economics

    def run(self, initial_state: SimulationState, config: ScenarioConfig, measures: list) -> ScenarioSummary:
        states: list[SimulationState] = []
        previous = initial_state
        for year in range(config.start_year, config.end_year + 1):
            if year == initial_state.year:
                state = SimulationState(
                    year=year,
                    electricity_base_kwh=initial_state.electricity_base_kwh,
                    natural_gas_m3=initial_state.natural_gas_m3,
                    coal_kg=initial_state.coal_kg,
                    oil_kg=initial_state.oil_kg,
                )
            else:
                state = BaselineEvolution.next_year(previous, year, config.growth_rates)

            results = [m.simulate(state, year) for m in measures if m.is_active(year)]
            EnergyBalance.apply(state, results)
            factors = self.factor_provider(year)
            state.carbon_emission_t = CarbonAccounting.calculate_tonnes(state.energy_amounts(), factors)
            state.metadata.update({f"ef_{k}": v for k, v in factors.items()})
            self.economics.evaluate(state, results)
            states.append(state)
            previous = state

        peak = PeakDetector.detect(states, config.peak_stability_years)
        neutral = NeutralityDetector.detect(states, config.neutrality_epsilon_t,
                                             config.neutrality_stability_years)
        return ScenarioSummary(
            name=config.name,
            peak_year=peak,
            neutral_year=neutral,
            cumulative_emission_t=sum(s.carbon_emission_t for s in states),
            cumulative_investment=sum(s.investment for s in states),
            cumulative_benefit=sum(s.annual_benefit for s in states),
            states=states,
        )
