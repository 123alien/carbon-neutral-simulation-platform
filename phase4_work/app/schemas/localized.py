from datetime import datetime
from pydantic import Field,model_validator
from .common import ORMModel
SITE_TYPES={"PARK","CAMPUS","PUBLIC_INSTITUTION","ENTERPRISE","STREET","OTHER"}
SYSTEM_TYPES={"ELECTRICITY","WATER","GAS","HEATING","COOLING","PV","WIND","STORAGE","HVAC","LIGHTING","EV_CHARGING","OTHER"}
class SiteCreate(ORMModel):
    enterprise_id:int;code:str;name:str;site_type:str;organization_node_id:int|None=None;address:str|None=None;area_m2:float|None=Field(default=None,ge=0);population:int|None=Field(default=None,ge=0);timezone:str="Asia/Shanghai";status:str="ACTIVE";metadata_json:dict=Field(default_factory=dict);longitude:float|None=None;latitude:float|None=None;position_json:dict|None=None;geometry_json:dict|None=None
    @model_validator(mode="after")
    def valid(self):
        self.site_type=self.site_type.upper()
        if self.site_type not in SITE_TYPES:raise ValueError("unsupported site_type")
        return self
class SiteRead(SiteCreate):id:int;created_at:datetime;updated_at:datetime
class BuildingCreate(ORMModel):
    organization_node_id:int|None=None;code:str;name:str;building_type:str;area_m2:float|None=Field(default=None,ge=0);floor_count:int|None=Field(default=None,ge=0);population:int|None=Field(default=None,ge=0);status:str="ACTIVE";metadata_json:dict=Field(default_factory=dict);longitude:float|None=None;latitude:float|None=None;position_json:dict|None=None;geometry_json:dict|None=None
class BuildingRead(BuildingCreate):id:int;site_id:int;created_at:datetime;updated_at:datetime
class EnergySystemCreate(ORMModel):
    site_id:int;building_id:int|None=None;code:str;name:str;system_type:str;status:str="ACTIVE";metadata_json:dict=Field(default_factory=dict)
    @model_validator(mode="after")
    def valid(self):
        self.system_type=self.system_type.upper()
        if self.system_type not in SYSTEM_TYPES:raise ValueError("unsupported system_type")
        return self
class EnergySystemRead(EnergySystemCreate):id:int;created_at:datetime;updated_at:datetime
class MeteringPointCreate(ORMModel):
    site_id:int;building_id:int|None=None;energy_system_id:int|None=None;device_id:int|None=None;data_source_id:int|None=None;code:str;name:str;metric_type:str;energy_type:str;unit:str;status:str="ACTIVE";metadata_json:dict=Field(default_factory=dict)
class MeteringPointRead(MeteringPointCreate):id:int;created_at:datetime;updated_at:datetime
