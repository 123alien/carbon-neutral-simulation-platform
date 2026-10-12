from datetime import datetime
from pydantic import Field
from .common import ORMModel
class SimulationBatchCreate(ORMModel):
    site_id:int|None=None
    enterprise_id:int;scenario_version_ids:list[int]=Field(min_length=2);baseline_scenario_version_id:int;year:int;electricity_price_per_kwh:float=Field(default=.57,ge=0);feed_in_tariff_per_kwh:float=Field(default=.42,ge=0);store_hourly_results:bool=True
class SimulationBatchItemRead(ORMModel):
    id:int;scenario_version_id:int;task_id:int|None=None;status:str;metrics_json:dict|None=None;error_message:str|None=None
class SimulationBatchRead(ORMModel):
    id:int;enterprise_id:int;baseline_scenario_version_id:int;status:str;request_snapshot_json:dict;comparison_json:dict|None=None;created_at:datetime;finished_at:datetime|None=None;items:list[SimulationBatchItemRead]
class RecommendationConvertRequest(ORMModel):
    name:str;description:str|None=None;base_year:int;start_year:int;end_year:int;target_peak_year:int|None=None;target_neutral_year:int|None=None
