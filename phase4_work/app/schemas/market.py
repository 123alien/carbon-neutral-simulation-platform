from datetime import datetime
from pydantic import Field, model_validator
from .common import ORMModel


class PriceFieldMapping(ORMModel):
    timestamp: str
    purchase_price: str
    feed_in_tariff: str | None = None


class PriceImportOptions(ORMModel):
    enterprise_id: int
    mapping: PriceFieldMapping
    timezone: str = "UTC"
    source: str | None = None
    preview_limit: int = Field(20, ge=1, le=200)


class FactorFieldMapping(ORMModel):
    timestamp: str
    factor: str


class FactorImportOptions(ORMModel):
    region: str
    version: str
    mapping: FactorFieldMapping
    timezone: str = "UTC"
    source: str | None = None
    preview_limit: int = Field(20, ge=1, le=200)


class MarketImportPreview(ORMModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    can_confirm: bool
    preview: list[dict]
    errors: list[dict]


class MarketImportConfirm(ORMModel):
    inserted_rows: int


class ElectricityPriceRead(ORMModel):
    timestamp: datetime
    purchase_price_per_kwh: float
    feed_in_tariff_per_kwh: float
    source: str | None = None


class GridFactorRead(ORMModel):
    timestamp: datetime
    region: str
    factor_kg_per_kwh: float
    source: str | None = None
    version: str


class GreenPowerContractCreate(ORMModel):
    enterprise_id: int
    name: str
    start_at: datetime
    end_at: datetime
    purchase_kwh: float | None = Field(default=None, gt=0)
    purchase_share: float | None = Field(default=None, gt=0, le=1)
    emission_factor_kg_per_kwh: float = Field(default=0, ge=0)
    premium_per_kwh: float = Field(default=0, ge=0)
    status: str = "ACTIVE"
    source: str | None = None


class GreenPowerContractRead(GreenPowerContractCreate):
    id: int
