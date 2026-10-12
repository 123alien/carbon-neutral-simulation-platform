from __future__ import annotations


class CarbonAccounting:
    """Generic carbon accounting using canonical physical energy units.

    factors are expected in kgCO2 per canonical unit:
      electricity: kgCO2/kWh
      natural_gas: kgCO2/m3
      coal: kgCO2/kg
      oil: kgCO2/kg
    """

    @staticmethod
    def calculate_tonnes(energy_amounts: dict[str, float], factors: dict[str, float]) -> float:
        kg = 0.0
        for energy_type, amount in energy_amounts.items():
            kg += max(float(amount), 0.0) * max(float(factors.get(energy_type, 0.0)), 0.0)
        return kg / 1000.0
