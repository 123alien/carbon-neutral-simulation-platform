from abc import ABC, abstractmethod
from app.simulation.types import SimulationState, MeasureResult

class MeasureModel(ABC):
    measure_type: str = "BASE"

    def __init__(self, start_year: int, end_year: int | None = None):
        self.start_year = start_year
        self.end_year = end_year

    def is_active(self, year: int) -> bool:
        return year >= self.start_year and (self.end_year is None or year <= self.end_year)

    @abstractmethod
    def simulate(self, state: SimulationState, year: int) -> MeasureResult:
        raise NotImplementedError
