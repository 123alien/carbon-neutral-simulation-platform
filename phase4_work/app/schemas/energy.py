from pydantic import Field, model_validator
from .common import ORMModel

class EnergyHistoryCreate(ORMModel):
    enterprise_id: int
    year: int = Field(ge=1900, le=2200)
    month: int | None = Field(default=None, ge=1, le=12)
    energy_type: str
    consumption: float = Field(ge=0)
    unit: str
    source: str | None = None

class EnergyHistoryRead(EnergyHistoryCreate):
    id: int

class EmissionFactorCreate(ORMModel):
    region: str
    year: int = Field(ge=1900, le=2200)
    energy_type: str
    factor: float = Field(ge=0)
    unit: str = "kgCO2/kWh"
    source: str | None = None
    version: str = "V1"

class EmissionFactorRead(EmissionFactorCreate):
    id: int


class GrowthEstimateRead(ORMModel):
    enterprise_id: int
    energy_type: str
    method: str
    rate: float
    years_used: list[int]
    canonical_unit: str
