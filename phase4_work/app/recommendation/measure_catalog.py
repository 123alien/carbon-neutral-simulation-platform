import json
from functools import lru_cache
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parents[2] / "P4_MEASURE_PARAMETER_CATALOG.json"


@lru_cache(maxsize=1)
def measure_catalog() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


def catalog_index() -> dict[str, dict]:
    return {item["measure_code"]: item for item in measure_catalog()["measures"]}


def p4_experiment_candidates(scale: str = "MEDIUM") -> dict[str, dict]:
    scale = scale.upper()
    if scale not in {"LOW", "MEDIUM", "HIGH"}:
        raise ValueError("experiment scale must be LOW, MEDIUM or HIGH")
    return {
        code: {
            "parameters": dict(item["experiment_parameters"][scale]),
            "enabled": bool(item["enabled"]),
            "recommendation_status": item["recommendation_status"],
            "parameter_sources": item["parameter_sources"],
        }
        for code, item in catalog_index().items()
    }


def validate_measure_parameters(code: str, parameters: dict) -> None:
    code = code.upper()
    item = catalog_index().get(code)
    if item is None:
        raise ValueError(f"measure {code} is not in the audited catalog")
    technical = item["technical_parameters"]
    aliases = {"capacity_kw": "rated_power_kw"} if code == "WIND" else {}
    for name, value in parameters.items():
        rule = technical.get(aliases.get(name, name))
        if not isinstance(rule, dict) or value is None or isinstance(value, (dict, list, str, bool)):
            continue
        number = float(value)
        if "min" in rule and number < float(rule["min"]):
            raise ValueError(f"{code}.{name} must be >= {rule['min']}")
        if "min_exclusive" in rule and number <= float(rule["min_exclusive"]):
            raise ValueError(f"{code}.{name} must be > {rule['min_exclusive']}")
        if "max" in rule and number > float(rule["max"]):
            raise ValueError(f"{code}.{name} must be <= {rule['max']}")
    if code == "STORAGE":
        low=float(parameters.get("soc_min",.1));initial=float(parameters.get("soc_initial",.5));high=float(parameters.get("soc_max",.9))
        if not 0 <= low <= initial <= high <= 1:raise ValueError("STORAGE requires soc_min <= soc_initial <= soc_max")
    if code == "WIND":
        cut_in=float(parameters.get("cut_in_speed_m_s",3));rated=float(parameters.get("rated_speed_m_s",12));cut_out=float(parameters.get("cut_out_speed_m_s",25))
        if not 0 <= cut_in < rated < cut_out:raise ValueError("WIND requires cut_in < rated < cut_out")
        mode=str(parameters.get("curve_mode","SIMPLE_CURVE")).upper()
        if mode in {"MANUFACTURER_CURVE","CALIBRATED_CURVE"} and len(parameters.get("power_curve") or []) < 2:raise ValueError(f"{mode} requires imported power_curve points")
