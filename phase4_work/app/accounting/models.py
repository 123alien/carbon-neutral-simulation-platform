from abc import ABC,abstractmethod
from dataclasses import dataclass

CANONICAL={
    "electricity":("kWh",{"wh":.001,"kwh":1,"mwh":1000}),
    "natural_gas":("m3",{"m3":1,"万m3":10000}),
    "coal":("kg",{"kg":1,"t":1000,"吨":1000}),
    "oil":("kg",{"kg":1,"t":1000,"吨":1000}),
    "heat":("kWh",{"kwh":1,"mwh":1000,"gj":277.7777777778}),
}
FACTOR_PATHS={
    # Additional official reporting-unit paths. Existing canonical paths remain
    # unchanged for backward compatibility with enterprise meter data.
    "natural_gas":{
        "kgco2/mmbtu":("MMBtu",{"mmbtu":1,"kbtu":.001,"thousandbtu":.001,"therm":.1,"gj":.947817120313}),
    },
    "oil":{
        "kgco2/gallon":("gallon",{"gallon":1,"gal":1}),
        "kgco2/mmbtu":("MMBtu",{"mmbtu":1,"kbtu":.001,"thousandbtu":.001,"gj":.947817120313}),
    },
    "heat":{
        "kgco2/mmbtu":("MMBtu",{"mmbtu":1,"kbtu":.001,"thousandbtu":.001,"therm":.1,"gj":.947817120313}),
    },
}
SCOPES={"electricity":"SCOPE_2","heat":"SCOPE_2","natural_gas":"SCOPE_1","coal":"SCOPE_1","oil":"SCOPE_1"}

@dataclass(frozen=True)
class AccountingCalculation:
    canonical_value:float;canonical_unit:str;scope:str;emission_t:float;formula:str

class CarbonAccountingModel(ABC):
    @abstractmethod
    def calculate(self,energy_type,value,unit,factor,factor_unit,scope=None)->AccountingCalculation:...

class EnergyCarbonAccountingModel(CarbonAccountingModel):
    def calculate(self,energy_type,value,unit,factor,factor_unit,scope=None):
        energy_type=energy_type.lower();unit_key=unit.lower().replace(" ","")
        if energy_type not in CANONICAL:raise ValueError(f"unsupported energy_type: {energy_type}")
        factor_key=factor_unit.lower().replace(" ","")
        path=FACTOR_PATHS.get(energy_type,{}).get(factor_key)
        canonical_unit,conversions=path or CANONICAL[energy_type]
        if unit_key not in conversions:raise ValueError(f"unsupported unit {unit} for {energy_type}")
        value=float(value)
        if value<0 or factor<0:raise ValueError("activity and factor must be non-negative")
        expected=f"kgco2/{canonical_unit.lower()}"
        if factor_key!=expected:raise ValueError(f"factor unit must be kgCO2/{canonical_unit}")
        canonical=value*conversions[unit_key];emission=canonical*float(factor)/1000
        return AccountingCalculation(canonical,canonical_unit,scope or SCOPES[energy_type],emission,f"{canonical:g} {canonical_unit} × {float(factor):g} kgCO2/{canonical_unit} ÷ 1000 = {emission:g} tCO2")

class CarbonAccountingRegistry:
    _models={}
    @classmethod
    def register(cls,name,model):cls._models[name]=model
    @classmethod
    def get(cls,name="ENERGY"):
        if name not in cls._models:raise ValueError(f"unknown accounting model: {name}")
        return cls._models[name]

CarbonAccountingRegistry.register("ENERGY",EnergyCarbonAccountingModel())
