from datetime import datetime
from pydantic import Field, model_validator
from .common import ORMModel

ALLOWED_MEASURES = {"PV", "WIND", "STORAGE", "HVAC", "LIGHTING", "EV_CHARGER", "GREEN_POWER"}
SCENARIO_TYPES = {"BASELINE", "ECONOMIC", "REDUCTION", "BALANCED", "CUSTOM"}

class ScenarioMeasureCreate(ORMModel):
    measure_type: str
    start_year: int
    end_year: int | None = None
    parameters_json: dict

    @model_validator(mode="after")
    def validate_measure(self):
        self.measure_type = self.measure_type.upper()
        if self.measure_type not in ALLOWED_MEASURES:
            raise ValueError(f"unsupported measure_type: {self.measure_type}")
        if self.end_year is not None and self.end_year < self.start_year:
            raise ValueError("end_year must be >= start_year")
        return self

class ScenarioCreate(ORMModel):
    enterprise_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    base_year: int
    start_year: int
    end_year: int
    target_peak_year: int | None = None
    target_neutral_year: int | None = None
    baseline_growth_json: dict = Field(default_factory=lambda: {"electricity": "auto", "natural_gas": "auto", "coal": 0.0, "oil": 0.0})
    status: str = "DRAFT"
    measures: list[ScenarioMeasureCreate] = Field(default_factory=list)
    scenario_type: str = "CUSTOM"

    @model_validator(mode="after")
    def validate_years(self):
        self.scenario_type = self.scenario_type.upper()
        if self.scenario_type not in SCENARIO_TYPES:
            raise ValueError(f"unsupported scenario_type: {self.scenario_type}")
        if self.start_year < self.base_year:
            raise ValueError("start_year must be >= base_year")
        if self.end_year < self.start_year:
            raise ValueError("end_year must be >= start_year")
        return self

class ScenarioMeasureRead(ScenarioMeasureCreate):
    id: int
    scenario_id: int

class ScenarioRead(ORMModel):
    id: int
    enterprise_id: int
    name: str
    description: str | None
    base_year: int
    start_year: int
    end_year: int
    target_peak_year: int | None
    target_neutral_year: int | None
    baseline_growth_json: dict
    status: str
    measures: list[ScenarioMeasureRead] = Field(default_factory=list)
    scenario_type: str = "CUSTOM"
    current_version_id: int | None = None
    created_at: datetime

class ScenarioVersionCreate(ORMModel):
    name: str|None=None;description:str|None=None;base_year:int;start_year:int;end_year:int;target_peak_year:int|None=None;target_neutral_year:int|None=None;baseline_growth_json:dict=Field(default_factory=dict);status:str="DRAFT";scenario_type:str="CUSTOM";measures:list[ScenarioMeasureCreate]=Field(default_factory=list)
    # Frozen experiment provenance belongs to the immutable version snapshot,
    # not to the mutable Scenario row.
    experiment_context: dict | None = None
    @model_validator(mode="after")
    def validate_version(self):
        self.scenario_type=self.scenario_type.upper()
        if self.scenario_type not in SCENARIO_TYPES:raise ValueError("unsupported scenario_type")
        if self.start_year<self.base_year or self.end_year<self.start_year:raise ValueError("invalid scenario years")
        return self
class ScenarioVersionRead(ORMModel):
    id:int;scenario_id:int;version_number:int;scenario_type:str;parameter_snapshot_json:dict;carbon_market_snapshot_json:dict|None=None;risk_parameter_snapshot_json:dict|None=None;source_recommendation_id:int|None=None;created_at:datetime
