from __future__ import annotations

import math
from statistics import median


class GrowthEstimator:
    """Estimate long-term baseline growth from historical annual totals.

    V0.3 uses a robust median year-on-year growth rate by default. It is less
    sensitive than a plain mean to one abnormal year. CAGR is also exposed for
    diagnostics.
    """

    @staticmethod
    def yoy_rates(year_values: list[tuple[int, float]]) -> list[float]:
        items = sorted((int(y), float(v)) for y, v in year_values if v is not None and v > 0)
        rates: list[float] = []
        for (_, prev), (_, cur) in zip(items, items[1:]):
            if prev > 0:
                rates.append(cur / prev - 1.0)
        return rates

    @classmethod
    def robust_rate(cls, year_values: list[tuple[int, float]], fallback: float = 0.0) -> float:
        rates = cls.yoy_rates(year_values)
        return float(median(rates)) if rates else float(fallback)

    @staticmethod
    def cagr(year_values: list[tuple[int, float]], fallback: float = 0.0) -> float:
        items = sorted((int(y), float(v)) for y, v in year_values if v is not None and v > 0)
        if len(items) < 2:
            return float(fallback)
        y0, v0 = items[0]
        y1, v1 = items[-1]
        years = y1 - y0
        if years <= 0 or v0 <= 0 or v1 <= 0:
            return float(fallback)
        return float(math.pow(v1 / v0, 1.0 / years) - 1.0)
