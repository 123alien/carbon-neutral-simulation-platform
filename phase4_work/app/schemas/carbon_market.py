from datetime import datetime
from pydantic import Field
from .common import ORMModel

class CarbonMarketScenarioCreate(ORMModel):
    scenario_version_id:int;carbon_price_per_t:float=Field(ge=0);carbon_quota_t:float=Field(ge=0);ccer_quantity_t:float=Field(default=0,ge=0);ccer_price_per_t:float=Field(default=0,ge=0);green_certificate_quantity:float=Field(default=0,ge=0);green_certificate_price:float=Field(default=0,ge=0)
class CarbonMarketScenarioRead(CarbonMarketScenarioCreate):
    id:int;created_at:datetime
class CarbonMarketIndicatorCreate(ORMModel):
    region:str;timestamp:datetime;carbon_price_per_t:float|None=Field(default=None,ge=0);carbon_quota_t:float|None=Field(default=None,ge=0);trading_volume_t:float|None=Field(default=None,ge=0);trading_amount_yuan:float|None=Field(default=None,ge=0);ccer_volume_t:float|None=Field(default=None,ge=0);ccer_price_per_t:float|None=Field(default=None,ge=0);ccer_trading_amount_yuan:float|None=Field(default=None,ge=0);green_certificate_volume:float|None=Field(default=None,ge=0);green_certificate_price:float|None=Field(default=None,ge=0);green_certificate_issued_count:float|None=Field(default=None,ge=0);green_certificate_traded_count:float|None=Field(default=None,ge=0);source:str
class CarbonMarketIndicatorBulkCreate(ORMModel):items:list[CarbonMarketIndicatorCreate]=Field(min_length=1)
class CarbonCostAssessmentCreate(ORMModel):
    scenario_version_id:int;task_id:int;gross_emission_t:float|None=Field(default=None,ge=0)
class CarbonCostAssessmentRead(ORMModel):
    id:int;scenario_version_id:int;task_id:int|None;gross_emission_t:float;input_snapshot_json:dict;result_json:dict;created_at:datetime
class RiskAssessmentCreate(ORMModel):
    scenario_version_id:int;simulation_task_id:int;batch_item_id:int|None=None;simulation_year:int|None=None;reduction_rate:float|None=None;payback_years:float|None=None;price_volatility_pct:float=Field(default=0,ge=0);renewable_volatility_pct:float=Field(default=0,ge=0);technical_implementation_score:float=Field(default=1,ge=0,le=1)
class RiskAssessmentRead(ORMModel):
    id:int;scenario_version_id:int;simulation_task_id:int;batch_item_id:int|None;input_snapshot_json:dict;results:list;overall_level:str;created_at:datetime
class FeasibilityReportCreate(ORMModel):
    enterprise_id:int;scenario_version_id:int;simulation_task_id:int;title:str="碳中和可行性与风险评估报告";batch_id:int|None=None;accounting_run_id:int|None=None;recommendation_run_id:int|None=None
class FeasibilityReportRead(ORMModel):
    id:int;enterprise_id:int;scenario_version_id:int;simulation_task_id:int;batch_id:int|None;accounting_run_id:int|None;recommendation_run_id:int|None;title:str;status:str;failure_reason:str|None=None;generated_at:datetime|None=None;input_snapshot_json:dict;report_data_json:dict;snapshot_created_at:datetime;files:list[dict];created_at:datetime
class ReportRenderRequest(ORMModel):formats:list[str]=Field(min_length=1)
class ReportFileRead(ORMModel):id:int;report_task_id:int;format:str;file_name:str;file_size:int;checksum:str;generated_at:datetime
