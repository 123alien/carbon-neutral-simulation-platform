from datetime import datetime
from pydantic import Field
from .common import ORMModel

class OrganizationNodeCreate(ORMModel):
    enterprise_id:int;parent_id:int|None=None;name:str;level:str;code:str|None=None;metadata_json:dict={}
class OrganizationNodeRead(OrganizationNodeCreate):id:int
class AccountingActivity(ORMModel):
    timestamp:datetime;energy_type:str;value:float=Field(ge=0);unit:str;organization_node_id:int|None=None;device_id:int|None=None;scope:str|None=None;source:str|None=None
class CarbonAccountingRunRequest(ORMModel):
    enterprise_id:int;name:str;period_start:datetime;period_end:datetime;scopes:list[str]=["SCOPE_1","SCOPE_2"];standard_basis:str="GHG Protocol Corporate Standard / ISO 14064-1";activities:list[AccountingActivity]=[];include_device_metrics:bool=False
class CarbonAccountingRunRead(ORMModel):
    id:int;enterprise_id:int;name:str;period_start:datetime;period_end:datetime;status:str;scopes_json:list;summary_json:dict;created_at:datetime
class CarbonAccountingResultRead(ORMModel):
    id:int;run_id:int;enterprise_id:int;organization_node_id:int|None=None;device_id:int|None=None;timestamp:datetime;energy_type:str;scope:str;activity_value:float;activity_unit:str;original_activity_value:float;original_activity_unit:str;emission_factor:float;factor_unit:str;factor_source:str|None=None;factor_version:str;formula:str;standard_basis:str;emission_t:float;activity_source:str|None=None
class AccountingStatisticsItem(ORMModel):
    bucket_start:datetime;dimension_key:str;emission_t:float;record_count:int
class AccountingStatisticsResponse(ORMModel):
    run_id:int;granularity:str;dimension:str;timezone:str;total_emission_t:float;items:list[AccountingStatisticsItem]
