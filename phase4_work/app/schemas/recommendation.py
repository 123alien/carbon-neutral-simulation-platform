from datetime import datetime
from pydantic import Field
from .common import ORMModel

class PathRecommendationRequest(ORMModel):
    site_id:int|None=None
    enterprise_id:int;simulation_year:int;target_peak_year:int|None=None;target_neutral_year:int|None=None;carbon_quota_t:float|None=Field(default=None,ge=0);energy_target_kwh:float|None=Field(default=None,ge=0);budget:float=Field(gt=0);top_n:int=Field(default=3,ge=1,le=10);weights:dict[str,dict[str,float]]={};candidate_parameters:dict[str,dict]={}
class RecommendedPathRead(ORMModel):
    id:int;profile:str;rank:int;score:float;measures_json:list;reasons_json:list;metrics_json:dict;validation_summary_json:dict
class RecommendationRunRead(ORMModel):
    id:int;enterprise_id:int;simulation_year:int;input_snapshot_json:dict;baseline_summary_json:dict;created_at:datetime;recommendations:list[RecommendedPathRead]
