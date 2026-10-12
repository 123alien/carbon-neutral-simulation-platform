from __future__ import annotations

from dataclasses import dataclass


class UnitConversionError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalEnergy:
    value: float
    unit: str


class UnitConverter:
    """Convert uploaded energy data into one canonical unit per energy type.

    Canonical units used by V0.3:
      electricity -> kWh
      natural_gas -> m3
      coal        -> kg
      oil         -> kg

    This deliberately avoids converting fuels to kWh-equivalent because official
    emission factors are frequently published per physical fuel unit.
    """

    _ALIASES = {
        "electricity": {
            "kwh": 1.0,
            "千瓦时": 1.0,
            "度": 1.0,
            "mwh": 1000.0,
            "gwh": 1_000_000.0,
        },
        "natural_gas": {
            "m3": 1.0,
            "m³": 1.0,
            "nm3": 1.0,
            "nm³": 1.0,
            "立方米": 1.0,
            "万m3": 10_000.0,
            "万m³": 10_000.0,
            "万立方米": 10_000.0,
        },
        "coal": {
            "kg": 1.0,
            "千克": 1.0,
            "公斤": 1.0,
            "t": 1000.0,
            "ton": 1000.0,
            "tonne": 1000.0,
            "吨": 1000.0,
        },
        "oil": {
            "kg": 1.0,
            "千克": 1.0,
            "公斤": 1.0,
            "t": 1000.0,
            "ton": 1000.0,
            "tonne": 1000.0,
            "吨": 1000.0,
        },
    }

    _CANONICAL_UNITS = {
        "electricity": "kWh",
        "natural_gas": "m3",
        "coal": "kg",
        "oil": "kg",
    }

    @classmethod
    def normalize_unit(cls, unit: str) -> str:
        return unit.strip().lower().replace(" ", "")

    @classmethod
    def canonical_unit(cls, energy_type: str) -> str:
        try:
            return cls._CANONICAL_UNITS[energy_type]
        except KeyError as exc:
            raise UnitConversionError(f"unsupported energy_type: {energy_type}") from exc

    @classmethod
    def convert(cls, energy_type: str, value: float, unit: str) -> CanonicalEnergy:
        if value < 0:
            raise UnitConversionError("energy consumption cannot be negative")
        normalized = cls.normalize_unit(unit)
        mapping = cls._ALIASES.get(energy_type)
        if mapping is None:
            raise UnitConversionError(f"unsupported energy_type: {energy_type}")
        if normalized not in mapping:
            allowed = ", ".join(sorted(mapping.keys()))
            raise UnitConversionError(
                f"unsupported unit for {energy_type}: {unit}; allowed units: {allowed}"
            )
        return CanonicalEnergy(value=float(value) * mapping[normalized], unit=cls.canonical_unit(energy_type))
