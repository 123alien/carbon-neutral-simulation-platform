from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GreenPowerAllocation:
    energy_kwh: float = 0.0
    emission_factor_kg_per_kwh: float = 0.0
    premium_cost: float = 0.0


class GreenPowerAllocator:
    def __init__(self, contracts: list[dict]):
        self.contracts = []
        for contract in contracts:
            item = dict(contract)
            item["remaining_kwh"] = item.get("purchase_kwh")
            self.contracts.append(item)

    def allocate(self, timestamp: datetime, grid_kwh: float) -> GreenPowerAllocation:
        remaining_grid = max(grid_kwh, 0.0); allocations = []
        for contract in self.contracts:
            if remaining_grid <= 0: break
            if not contract["start_at"] <= timestamp < contract["end_at"]: continue
            share = contract.get("purchase_share")
            requested = remaining_grid * float(share) if share is not None else remaining_grid
            cap = contract.get("remaining_kwh")
            if cap is not None: requested = min(requested, max(float(cap), 0.0))
            energy = min(requested, remaining_grid)
            if energy <= 0: continue
            if cap is not None: contract["remaining_kwh"] = max(float(cap) - energy, 0.0)
            allocations.append((energy, float(contract.get("emission_factor_kg_per_kwh", 0)), float(contract.get("premium_per_kwh", 0))))
            remaining_grid -= energy
        total = sum(item[0] for item in allocations)
        factor = sum(energy * factor for energy, factor, _ in allocations) / total if total else 0.0
        premium = sum(energy * price for energy, _, price in allocations)
        return GreenPowerAllocation(total, factor, premium)
