from dataclasses import dataclass
from math import cos, radians


@dataclass(frozen=True)
class SolarInput:
    ghi_w_m2: float
    temperature_c: float | None = None
    poa_w_m2: float | None = None
    module_temperature_c: float | None = None


class SolarIrradianceModel:
    """Extensible irradiance-to-AC model with backward-compatible defaults."""

    def __init__(self, config: dict):
        self.config = config

    def plane_of_array(self, point: SolarInput) -> float:
        mode = str(self.config.get("irradiance_mode", "GHI")).upper()
        if mode == "GHI":
            return max(float(point.ghi_w_m2), 0.0)
        if mode != "POA":
            raise ValueError("irradiance_mode must be GHI or POA")
        if point.poa_w_m2 is not None:
            return max(float(point.poa_w_m2), 0.0)
        # V1 transposition fallback is orientation-only and uses no future data.
        tilt = max(min(float(self.config.get("tilt_deg", 0.0)), 90.0), 0.0)
        azimuth = float(self.config.get("azimuth_deg", 180.0)) % 360
        azimuth_factor = max(cos(radians(abs(azimuth - 180.0))), 0.0)
        tilt_factor = max(cos(radians(tilt)), 0.0)
        factor = float(self.config.get("poa_transposition_factor", tilt_factor * (0.7 + 0.3 * azimuth_factor)))
        return max(float(point.ghi_w_m2) * max(factor, 0.0), 0.0)

    def ac_power_kw(self, point: SolarInput, capacity_kw: float, degradation_factor: float = 1.0) -> float:
        irradiance = self.plane_of_array(point)
        performance_ratio = max(float(self.config.get("performance_ratio", self.config.get("system_efficiency", 0.85))), 0.0)
        inverter_efficiency = max(min(float(self.config.get("inverter_efficiency", 1.0)), 1.0), 0.0)
        temperature_factor = 1.0
        cell_temperature = point.module_temperature_c
        if cell_temperature is None and point.temperature_c is not None:
            noct = float(self.config.get("noct_c", 45.0))
            cell_temperature = float(point.temperature_c) + irradiance / 800.0 * (noct - 25.0)
        if cell_temperature is not None:
            coefficient = float(self.config.get("temperature_coefficient_per_c", -0.004))
            temperature_factor = max(1.0 + coefficient * (float(cell_temperature) - 25.0), 0.0)
        return max(capacity_kw, 0.0) * irradiance / 1000.0 * performance_ratio * inverter_efficiency * max(degradation_factor, 0.0) * temperature_factor

    def ac_energy_kwh(self, point: SolarInput, capacity_kw: float, degradation_factor: float, interval_hours: float = 1.0) -> float:
        """Backward-compatible energy API; power and interval are now explicit."""
        return self.ac_power_kw(point,capacity_kw,degradation_factor)*max(float(interval_hours),0.0)
