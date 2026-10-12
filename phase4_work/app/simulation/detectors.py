from app.simulation.types import SimulationState

class PeakDetector:
    @staticmethod
    def detect(states: list[SimulationState], stability_years: int = 3) -> int | None:
        if len(states) <= stability_years:
            return None
        emissions = [s.carbon_emission_t for s in states]
        for i in range(0, len(states) - stability_years):
            if emissions[i] == max(emissions[: i + stability_years + 1]):
                tail = emissions[i:i + stability_years + 1]
                if all(tail[j] > tail[j + 1] for j in range(len(tail) - 1)):
                    return states[i].year
        return None

class NeutralityDetector:
    @staticmethod
    def detect(states: list[SimulationState], epsilon_t: float = 1.0, stability_years: int = 3) -> int | None:
        for i in range(0, len(states) - stability_years + 1):
            window = states[i:i + stability_years]
            if len(window) == stability_years and all(s.carbon_emission_t <= epsilon_t for s in window):
                return states[i].year
        return None
