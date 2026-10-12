from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StorageDispatch:
    pv_charge_kwh: float
    grid_charge_kwh: float
    discharge_kwh: float
    soc_kwh: float

    @property
    def charge_kwh(self) -> float:
        return self.pv_charge_kwh + self.grid_charge_kwh


class HourlyStorageModel:
    STRATEGIES = {"PV_SELF_CONSUMPTION", "PEAK_VALLEY_ARBITRAGE"}

    def __init__(self, config: dict):
        self.capacity = max(float(config.get("capacity_kwh", 0)), 0)
        self.max_charge = max(float(config.get("max_charge_kw", self.capacity)), 0)
        self.max_discharge = max(float(config.get("max_discharge_kw", self.capacity)), 0)
        self.charge_eff = float(config.get("charge_efficiency", 0.95))
        self.discharge_eff = float(config.get("discharge_efficiency", 0.95))
        if not 0 < self.charge_eff <= 1 or not 0 < self.discharge_eff <= 1:
            raise ValueError("storage efficiencies must be in (0, 1]")
        self.soc_min = float(config.get("soc_min", 0.1)) * self.capacity
        self.soc_max = float(config.get("soc_max", 0.9)) * self.capacity
        initial = float(config.get("soc_initial", 0.5)) * self.capacity
        if not 0 <= self.soc_min <= initial <= self.soc_max <= self.capacity:
            raise ValueError("storage SOC boundaries are invalid")
        self.soc = initial
        self.strategy = str(config.get("strategy", "PV_SELF_CONSUMPTION")).upper()
        if self.strategy not in self.STRATEGIES:
            raise ValueError("unsupported storage strategy")
        self.peak_hours = {int(hour) for hour in config.get("peak_hours", range(8, 22))}
        self.off_peak_hours = {int(hour) for hour in config.get("off_peak_hours", range(0, 7))}

    def _charge_limit(self) -> float:
        return min(self.max_charge, max((self.soc_max - self.soc) / self.charge_eff, 0.0))

    def dispatch(self, timestamp: datetime, surplus_pv_kwh: float, deficit_kwh: float) -> StorageDispatch:
        pv_charge = min(max(surplus_pv_kwh, 0), self._charge_limit())
        grid_charge = discharge = 0.0
        if pv_charge > 0:
            self.soc += pv_charge * self.charge_eff
        elif self.strategy == "PEAK_VALLEY_ARBITRAGE" and timestamp.hour in self.off_peak_hours:
            grid_charge = self._charge_limit()
            self.soc += grid_charge * self.charge_eff
        elif deficit_kwh > 0 and (self.strategy == "PV_SELF_CONSUMPTION" or timestamp.hour in self.peak_hours):
            discharge = min(deficit_kwh, self.max_discharge, max((self.soc - self.soc_min) * self.discharge_eff, 0.0))
            self.soc -= discharge / self.discharge_eff
        self.soc = min(max(self.soc, self.soc_min), self.soc_max)
        if (pv_charge + grid_charge) > 0 and discharge > 0:
            raise RuntimeError("battery cannot charge and discharge simultaneously")
        return StorageDispatch(pv_charge, grid_charge, discharge, self.soc)
