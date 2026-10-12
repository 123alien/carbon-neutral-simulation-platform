from app.simulation.types import SimulationState, MeasureResult

class EnergyBalance:
    @staticmethod
    def apply(state: SimulationState, results: list[MeasureResult]) -> SimulationState:
        saving = sum(r.energy_saved_kwh for r in results)
        generation = sum(r.generation_kwh for r in results)
        after_saving = max(state.electricity_base_kwh - saving, 0.0)
        self_use = min(generation, after_saving)
        export = max(generation - self_use, 0.0)
        grid = max(after_saving - self_use, 0.0)
        state.energy_saved_kwh = saving
        state.electricity_after_saving_kwh = after_saving
        state.pv_generation_kwh = generation
        state.pv_self_use_kwh = self_use
        state.pv_export_kwh = export
        state.grid_power_kwh = grid
        state.investment = sum(r.investment for r in results)
        return state
