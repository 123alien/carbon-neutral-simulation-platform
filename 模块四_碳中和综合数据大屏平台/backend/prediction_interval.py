"""Reproducible model prediction intervals for long-term campus simulations.

The upstream engine currently returns deterministic annual paths.  This module
propagates explicitly documented uncertainty in the two compounding assumptions
that dominate purchased-electricity emissions: annual load growth and annual
grid-factor change.  It never labels the result as observed-data calibration.
"""
from __future__ import annotations

import math
import random


CONFIDENCE_LEVEL = 0.95
SAMPLE_SIZE = 2000


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def build_prediction_interval(result: dict, assumptions: dict, run_id: int) -> dict | None:
    annual = result.get("annual") or []
    if len(annual) < 2:
        return None

    load_growth = float(assumptions.get("annual_load_growth_rate") or 0.0)
    grid_change = float(assumptions.get("annual_grid_factor_change_rate") or 0.0)
    # Demonstration calibration: 20% relative standard deviation with a 0.25
    # percentage-point floor, plus 1.5% baseline emissions-factor uncertainty.
    load_sigma = max(0.0025, abs(load_growth) * 0.20)
    grid_sigma = max(0.0025, abs(grid_change) * 0.20)
    baseline_factor_sigma = 0.015
    rng = random.Random(f"HBUE:{run_id}:prediction-interval:v1")
    samples = [
        (
            rng.gauss(load_growth, load_sigma),
            rng.gauss(grid_change, grid_sigma),
            max(0.0, rng.gauss(1.0, baseline_factor_sigma)),
        )
        for _ in range(SAMPLE_SIZE)
    ]

    start_year = int(annual[0]["year"])
    points = []
    for row in annual:
        horizon = max(0, int(row["year"]) - start_year)
        gross = max(0.0, float(row.get("gross_emission_t", row.get("net_emission_t", 0.0)) or 0.0))
        net = max(0.0, float(row.get("net_emission_t") or 0.0))
        fixed_reduction = max(0.0, gross - net)
        outcomes = []
        for sampled_load, sampled_grid, baseline_factor in samples:
            load_ratio = ((1 + sampled_load) / max(1e-9, 1 + load_growth)) ** horizon
            grid_ratio = ((1 + sampled_grid) / max(1e-9, 1 + grid_change)) ** horizon
            sampled_gross = gross * baseline_factor * load_ratio * grid_ratio
            outcomes.append(max(0.0, sampled_gross - fixed_reduction))
        points.append({
            "year": int(row["year"]),
            "mean_t": round(net, 6),
            "p10_t": round(_quantile(outcomes, 0.10), 6),
            "p50_t": round(_quantile(outcomes, 0.50), 6),
            "p90_t": round(_quantile(outcomes, 0.90), 6),
            "lower_t": round(_quantile(outcomes, 0.025), 6),
            "upper_t": round(_quantile(outcomes, 0.975), 6),
        })

    return {
        "confidence_level": CONFIDENCE_LEVEL,
        "interval_type": "PREDICTION_INTERVAL",
        "method": "MONTE_CARLO_PARAMETER_PROPAGATION",
        "method_name": "Monte Carlo参数不确定性传播",
        "sample_size": SAMPLE_SIZE,
        "data_class": "DEMO_MODEL_INTERVAL",
        "calibration_notice": "演示校准：未使用学校历史预测误差，不能替代实测回测置信区间。",
        "assumptions": {
            "annual_load_growth_rate_mean": load_growth,
            "annual_load_growth_rate_std": load_sigma,
            "annual_grid_factor_change_rate_mean": grid_change,
            "annual_grid_factor_change_rate_std": grid_sigma,
            "baseline_emission_factor_relative_std": baseline_factor_sigma,
        },
        "points": points,
    }
