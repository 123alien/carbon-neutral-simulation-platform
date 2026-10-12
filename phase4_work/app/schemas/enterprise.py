from datetime import datetime
from pydantic import Field
from .common import ORMModel

class EnterpriseCreate(ORMModel):
    name: str = Field(min_length=1, max_length=200)
    region: str | None = None
    industry: str | None = None
    building_area: float | None = Field(default=None, ge=0)
    population: int | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    base_year: int = Field(ge=1900, le=2200)

class EnterpriseUpdate(ORMModel):
    name: str | None = None
    region: str | None = None
    industry: str | None = None
    building_area: float | None = Field(default=None, ge=0)
    population: int | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    base_year: int | None = Field(default=None, ge=1900, le=2200)

class EnterpriseRead(EnterpriseCreate):
    id: int
    created_at: datetime
    updated_at: datetime
