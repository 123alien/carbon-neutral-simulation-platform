from datetime import datetime
from pydantic import Field
from .common import ORMModel

class DataSourceCreate(ORMModel):
    enterprise_id:int; site_id:int|None=None; building_id:int|None=None; device_id:int|None=None; metering_point_id:int|None=None; data_nature:str|None=None; name:str=Field(min_length=1,max_length=200); source_type:str; config_json:dict={}; credentials:dict|None=None; status:str="ACTIVE";collection_mode:str="MANUAL";schedule_enabled:bool=False;interval_minutes:int|None=None
class DataSourceUpdate(ORMModel):
    name:str|None=None; site_id:int|None=None; building_id:int|None=None; device_id:int|None=None; metering_point_id:int|None=None; data_nature:str|None=None; config_json:dict|None=None; credentials:dict|None=None; status:str|None=None;collection_mode:str|None=None;schedule_enabled:bool|None=None;interval_minutes:int|None=None
class DataSourceRead(ORMModel):
    id:int; enterprise_id:int; site_id:int|None=None; building_id:int|None=None; device_id:int|None=None; metering_point_id:int|None=None; data_nature:str|None=None; name:str; source_type:str; config_json:dict; status:str; has_credentials:bool;collection_mode:str;schedule_enabled:bool;interval_minutes:int|None=None; last_sync_at:datetime|None=None; created_at:datetime; updated_at:datetime
class AcquisitionConfig(ORMModel):collection_mode:str;enabled:bool;interval_minutes:int|None=None
class DeviceCreate(ORMModel):
    enterprise_id:int; data_source_id:int|None=None; external_id:str; name:str; device_type:str; metadata_json:dict={}; status:str="ACTIVE";longitude:float|None=None;latitude:float|None=None;position_json:dict|None=None;geometry_json:dict|None=None
class DeviceRead(DeviceCreate): id:int; created_at:datetime
class DeviceMetricRead(ORMModel):
    id:int; device_id:int; data_source_id:int; timestamp:datetime; metric_name:str; value:float; unit:str; quality:str
class ConnectionTestRead(ORMModel): success:bool; message:str; status_code:int|None=None
class SyncResultRead(ORMModel): extracted:int; inserted:int; quarantined:int; warnings:int
class DataQualityRead(ORMModel): data_source_id:int; total_records:int; valid_records:int; quarantined_records:int; warning_records:int; quality_rate:float; by_stage:dict[str,int]
