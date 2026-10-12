from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Iterable
from .solar import SolarInput, SolarIrradianceModel
from .storage import HourlyStorageModel
from .green_power import GreenPowerAllocation
from .device_models import HourlyDeviceModelRegistry


@dataclass
class HourlyInput:
    timestamp: datetime
    load_kwh: float
    irradiation_wm2: float = 0.0
    temperature_c: float | None = None
    humidity_pct: float | None = None
    poa_w_m2: float | None = None
    purchase_price_per_kwh: float | None = None
    feed_in_tariff_per_kwh: float | None = None
    grid_emission_factor_kg_per_kwh: float | None = None
    wind_speed_m_s: float | None = None
    existing_pv_kwh: float = 0.0
    existing_ev_kwh: float = 0.0
    direct_emission_t: float = 0.0


@dataclass
class HourlyResult:
    timestamp: datetime
    load_base_kwh: float
    hvac_saved_kwh: float
    lighting_saved_kwh: float
    load_after_saving_kwh: float
    pv_generation_kwh: float
    pv_self_use_kwh: float
    pv_export_kwh: float
    grid_power_kwh: float
    carbon_emission_t: float
    electricity_cost: float
    feed_in_revenue: float
    storage_charge_kwh: float = 0.0
    storage_discharge_kwh: float = 0.0
    storage_soc_kwh: float = 0.0
    curtailed_pv_kwh: float = 0.0
    energy_balance_error_kwh: float = 0.0
    purchase_price_per_kwh: float = 0.0
    feed_in_tariff_per_kwh: float = 0.0
    grid_emission_factor_kg_per_kwh: float = 0.0
    green_power_kwh: float = 0.0
    green_power_emission_t: float = 0.0
    green_power_carbon_reduction_t: float = 0.0
    ev_charging_load_kwh: float = 0.0
    wind_generation_kwh: float = 0.0
    wind_self_use_kwh: float = 0.0
    wind_export_kwh: float = 0.0
    renewable_generation_kwh: float = 0.0
    renewable_export_kwh: float = 0.0
    curtailed_renewable_kwh: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class HourlySummary:
    year: int
    hours: int
    load_base_kwh: float
    energy_saved_kwh: float
    pv_generation_kwh: float
    pv_self_use_kwh: float
    pv_export_kwh: float
    grid_power_kwh: float
    carbon_emission_t: float
    electricity_cost: float
    feed_in_revenue: float
    pv_self_consumption_rate: float
    pv_load_coverage_rate: float
    storage_charge_kwh: float = 0.0
    storage_discharge_kwh: float = 0.0
    curtailed_pv_kwh: float = 0.0
    ending_storage_soc_kwh: float = 0.0
    green_power_kwh: float = 0.0
    green_power_carbon_reduction_t: float = 0.0
    ev_charging_load_kwh: float = 0.0
    wind_generation_kwh: float = 0.0
    wind_self_use_kwh: float = 0.0
    wind_export_kwh: float = 0.0
    renewable_generation_kwh: float = 0.0
    renewable_export_kwh: float = 0.0
    curtailed_renewable_kwh: float = 0.0


class HourlySimulationEngine:
    """Deterministic hourly electricity simulation for V1 Phase 4.

    Assumptions:
    - each record represents one hour and load_kwh is interval energy;
    - irradiation_wm2 is average irradiance during that hour;
    - HVAC and lighting saving are applied before PV energy balance;
    - PV AC output uses capacity_kw * irradiance/1000 * performance_ratio;
    - no storage in Phase 4; excess PV is exported.
    """

    def __init__(
        self,
        electricity_factor_kg_per_kwh: float,
        electricity_price_per_kwh: float = 0.57,
        feed_in_tariff_per_kwh: float = 0.42,
    ):
        if electricity_factor_kg_per_kwh < 0:
            raise ValueError("electricity emission factor must be >= 0")
        self.ef = electricity_factor_kg_per_kwh
        self.price = electricity_price_per_kwh
        self.feed_in = feed_in_tariff_per_kwh

    @staticmethod
    def _active(params: dict, ts: datetime) -> bool:
        start_year = int(params.get("start_year", ts.year))
        end_year = params.get("end_year")
        return ts.year >= start_year and (end_year is None or ts.year <= int(end_year))

    def run(self, points: Iterable[HourlyInput], config: dict, green_power_allocator=None) -> tuple[list[HourlyResult], HourlySummary]:
        rows = list(points)
        if not rows:
            raise ValueError("hourly profile is empty")

        pv = dict(config.get("pv") or {})
        hvac = dict(config.get("hvac") or {})
        lighting = dict(config.get("lighting") or {})
        storage_config = dict(config.get("storage") or {})
        storage = HourlyStorageModel(storage_config) if storage_config else None
        solar = SolarIrradianceModel(pv)
        wind_config=dict(config.get("wind") or {});ev_config=dict(config.get("ev_charger") or {})
        wind_model=HourlyDeviceModelRegistry.create("WIND",wind_config) if wind_config else None
        ev_model=HourlyDeviceModelRegistry.create("EV_CHARGER",ev_config) if ev_config else None
        result: list[HourlyResult] = []

        for p in rows:
            if p.load_kwh < 0 or p.irradiation_wm2 < 0:
                raise ValueError("load and irradiation must be >= 0")
            facility_load = float(p.load_kwh)
            ev_load = p.existing_ev_kwh+(ev_model.simulate(p.timestamp,{}) if ev_model and self._active(ev_config,p.timestamp) else 0.0)
            load = facility_load + ev_load

            hvac_saved = 0.0
            if hvac and self._active(hvac, p.timestamp):
                share = max(0.0, min(float(hvac.get("load_share", 0.0)), 1.0))
                saving_rate = max(0.0, min(float(hvac.get("saving_rate", 0.0)), 1.0))
                hvac_saved = facility_load * share * saving_rate

            lighting_saved = 0.0
            if lighting and self._active(lighting, p.timestamp):
                if "load_share" in lighting:
                    share = max(0.0, min(float(lighting.get("load_share", 0.0)), 1.0))
                    saving_rate = max(0.0, min(float(lighting.get("saving_rate", 0.0)), 1.0))
                    lighting_saved = facility_load * share * saving_rate
                else:
                    qty = max(float(lighting.get("quantity", 0.0)), 0.0)
                    p_before = max(float(lighting.get("power_before_w", 0.0)), 0.0)
                    p_after = max(float(lighting.get("power_after_w", p_before)), 0.0)
                    operating = float(lighting.get("operating_fraction", 1.0))
                    operating = max(0.0, min(operating, 1.0))
                    lighting_saved = qty * max(p_before - p_after, 0.0) / 1000.0 * operating

            total_saved = min(hvac_saved + lighting_saved, facility_load)
            # Preserve proportional contributions when savings exceed interval load.
            if hvac_saved + lighting_saved > facility_load and hvac_saved + lighting_saved > 0:
                scale = facility_load / (hvac_saved + lighting_saved)
                hvac_saved *= scale
                lighting_saved *= scale
            load_after = max(load - total_saved, 0.0)

            pv_generation = 0.0
            if pv and self._active(pv, p.timestamp):
                capacity_kw = max(float(pv.get("capacity_kw", 0.0)), 0.0)
                pr = max(float(pv.get("performance_ratio", pv.get("system_efficiency", 0.85))), 0.0)
                degradation = max(float(pv.get("degradation_rate", 0.007)), 0.0)
                start_year = int(pv.get("start_year", p.timestamp.year))
                age = max(p.timestamp.year - start_year, 0)
                degradation_factor = max((1.0 - degradation) ** age, 0.0)
                pv_generation = solar.ac_energy_kwh(SolarInput(p.irradiation_wm2, p.temperature_c, p.poa_w_m2), capacity_kw, degradation_factor)

            pv_generation+=p.existing_pv_kwh
            wind_generation=wind_model.simulate(p.timestamp,{"wind_speed_m_s":p.wind_speed_m_s}) if wind_model and self._active(wind_config,p.timestamp) else 0.0
            renewable_generation=pv_generation+wind_generation

            pv_direct = min(load_after, pv_generation)
            wind_direct=min(max(load_after-pv_direct,0),wind_generation)
            deficit = max(load_after - renewable_generation, 0.0)
            surplus = max(renewable_generation - load_after, 0.0)
            dispatch = storage.dispatch(p.timestamp, surplus, deficit) if storage and self._active(storage_config, p.timestamp) else None
            charge = dispatch.charge_kwh if dispatch else 0.0
            discharge = dispatch.discharge_kwh if dispatch else 0.0
            renewable_charge = dispatch.pv_charge_kwh if dispatch else 0.0
            grid_charge = dispatch.grid_charge_kwh if dispatch else 0.0
            soc = dispatch.soc_kwh if dispatch else 0.0
            remaining_surplus = max(surplus - renewable_charge, 0.0)
            export_limit = pv.get("export_limit_kw")
            export = remaining_surplus if export_limit is None else min(remaining_surplus, max(float(export_limit), 0.0))
            curtailed = max(remaining_surplus - export, 0.0)
            grid = max(deficit - discharge, 0.0) + grid_charge
            surplus_pv=max(pv_generation-pv_direct,0);surplus_wind=max(wind_generation-wind_direct,0);surplus_total=surplus_pv+surplus_wind
            pv_share=surplus_pv/surplus_total if surplus_total else 0;wind_share=surplus_wind/surplus_total if surplus_total else 0
            pv_charge=renewable_charge*pv_share;wind_charge=renewable_charge*wind_share
            pv_export=export*pv_share;wind_export=export*wind_share;pv_curtailed=curtailed*pv_share
            self_use = pv_direct + pv_charge
            wind_self_use=wind_direct+wind_charge
            balance_error = (grid + renewable_generation + discharge) - (load_after + charge + export + curtailed)
            if abs(balance_error) > 1e-7:
                raise RuntimeError(f"hourly energy balance failed: {balance_error}")
            allocation = green_power_allocator.allocate(p.timestamp, grid) if green_power_allocator else GreenPowerAllocation()
            green_kwh = min(allocation.energy_kwh, grid)
            grid_factor = float(p.grid_emission_factor_kg_per_kwh if p.grid_emission_factor_kg_per_kwh is not None else self.ef)
            green_emission_t = green_kwh * allocation.emission_factor_kg_per_kwh / 1000.0
            green_reduction_t = green_kwh * max(grid_factor - allocation.emission_factor_kg_per_kwh, 0.0) / 1000.0
            carbon_t = ((grid - green_kwh) * grid_factor) / 1000.0 + green_emission_t+p.direct_emission_t
            hourly_price = p.purchase_price_per_kwh if p.purchase_price_per_kwh is not None else self.price
            if p.purchase_price_per_kwh is None and storage and storage.strategy == "PEAK_VALLEY_ARBITRAGE":
                if p.timestamp.hour in storage.off_peak_hours:
                    hourly_price = float(storage_config.get("off_peak_price_per_kwh", self.price))
                elif p.timestamp.hour in storage.peak_hours:
                    hourly_price = float(storage_config.get("peak_price_per_kwh", self.price))
                else:
                    hourly_price = float(storage_config.get("shoulder_price_per_kwh", self.price))
            hourly_tariff = float(p.feed_in_tariff_per_kwh if p.feed_in_tariff_per_kwh is not None else self.feed_in)
            cost = grid * hourly_price + allocation.premium_cost
            revenue = export * hourly_tariff
            result.append(HourlyResult(
                timestamp=p.timestamp,
                load_base_kwh=load,
                hvac_saved_kwh=hvac_saved,
                lighting_saved_kwh=lighting_saved,
                load_after_saving_kwh=load_after,
                pv_generation_kwh=pv_generation,
                pv_self_use_kwh=self_use,
                pv_export_kwh=pv_export,
                grid_power_kwh=grid,
                carbon_emission_t=carbon_t,
                electricity_cost=cost,
                feed_in_revenue=revenue,
                storage_charge_kwh=charge,
                storage_discharge_kwh=discharge,
                storage_soc_kwh=soc,
                curtailed_pv_kwh=pv_curtailed,
                energy_balance_error_kwh=balance_error,
                purchase_price_per_kwh=hourly_price,
                feed_in_tariff_per_kwh=hourly_tariff,
                grid_emission_factor_kg_per_kwh=grid_factor,
                green_power_kwh=green_kwh,
                green_power_emission_t=green_emission_t,
                green_power_carbon_reduction_t=green_reduction_t,
                ev_charging_load_kwh=ev_load,
                wind_generation_kwh=wind_generation,
                wind_self_use_kwh=wind_self_use,
                wind_export_kwh=wind_export,
                renewable_generation_kwh=renewable_generation,
                renewable_export_kwh=export,
                curtailed_renewable_kwh=curtailed,
            ))

        total = lambda name: sum(float(getattr(r, name)) for r in result)
        pv_total = total("pv_generation_kwh")
        load_total = total("load_base_kwh")
        summary = HourlySummary(
            year=rows[0].timestamp.year,
            hours=len(result),
            load_base_kwh=load_total,
            energy_saved_kwh=total("hvac_saved_kwh") + total("lighting_saved_kwh"),
            pv_generation_kwh=pv_total,
            pv_self_use_kwh=total("pv_self_use_kwh"),
            pv_export_kwh=total("pv_export_kwh"),
            grid_power_kwh=total("grid_power_kwh"),
            carbon_emission_t=total("carbon_emission_t"),
            electricity_cost=total("electricity_cost"),
            feed_in_revenue=total("feed_in_revenue"),
            pv_self_consumption_rate=(total("pv_self_use_kwh") / pv_total if pv_total > 0 else 0.0),
            pv_load_coverage_rate=(total("pv_self_use_kwh") / load_total if load_total > 0 else 0.0),
            storage_charge_kwh=total("storage_charge_kwh"),
            storage_discharge_kwh=total("storage_discharge_kwh"),
            curtailed_pv_kwh=total("curtailed_pv_kwh"),
            ending_storage_soc_kwh=result[-1].storage_soc_kwh,
            green_power_kwh=total("green_power_kwh"),
            green_power_carbon_reduction_t=total("green_power_carbon_reduction_t"),
            ev_charging_load_kwh=total("ev_charging_load_kwh"),
            wind_generation_kwh=total("wind_generation_kwh"),
            wind_self_use_kwh=total("wind_self_use_kwh"),
            wind_export_kwh=total("wind_export_kwh"),
            renewable_generation_kwh=total("renewable_generation_kwh"),
            renewable_export_kwh=total("renewable_export_kwh"),
            curtailed_renewable_kwh=total("curtailed_renewable_kwh"),
        )
        return result, summary
