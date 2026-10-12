from abc import ABC,abstractmethod
from datetime import datetime

class HourlyDeviceModel(ABC):
    @abstractmethod
    def simulate(self,timestamp:datetime,context:dict)->float:...

class HourlyDeviceModelRegistry:
    _models={}
    @classmethod
    def register(cls,name,model_cls):cls._models[name.upper()]=model_cls
    @classmethod
    def create(cls,name,config):
        key=name.upper()
        if key not in cls._models:raise ValueError(f"unknown hourly device model: {name}")
        return cls._models[key](config)
    @classmethod
    def available(cls):return sorted(cls._models)

class WindGenerationModel(HourlyDeviceModel):
    def __init__(self,config):
        self.config=config;self.rated_power=max(float(config.get("rated_power_kw",0)),0);self.cut_in=float(config.get("cut_in_speed_m_s",3));self.rated_speed=float(config.get("rated_speed_m_s",12));self.cut_out=float(config.get("cut_out_speed_m_s",25));self.curve=sorted([(float(item.get("wind_speed_m_s")),float(item.get("power_fraction"))) if isinstance(item,dict) else (float(item[0]),float(item[1])) for item in config.get("power_curve",[])])
        self.mode=str(config.get("curve_mode","MANUFACTURER_CURVE" if self.curve else "SIMPLE_CURVE")).upper()
        if self.mode not in {"SIMPLE_CURVE","MANUFACTURER_CURVE","CALIBRATED_CURVE"}:raise ValueError("curve_mode must be SIMPLE_CURVE, MANUFACTURER_CURVE or CALIBRATED_CURVE")
        if self.mode in {"MANUFACTURER_CURVE","CALIBRATED_CURVE"} and len(self.curve)<2:raise ValueError(f"{self.mode} requires at least two imported power-curve points")
        self.reference_air_density=max(float(config.get("reference_air_density_kg_m3",1.225)),.1)
        if not 0<=self.cut_in<self.rated_speed<self.cut_out:raise ValueError("wind speed thresholds must satisfy cut_in < rated < cut_out")
    def _fraction(self,speed):
        if speed<self.cut_in or speed>=self.cut_out:return 0
        if self.curve:
            if speed<=self.curve[0][0]:return max(min(self.curve[0][1],1),0)
            for (x0,y0),(x1,y1) in zip(self.curve,self.curve[1:]):
                if x0<=speed<=x1:return max(min(y0+(y1-y0)*(speed-x0)/(x1-x0),1),0)
            return max(min(self.curve[-1][1],1),0)
        if speed>=self.rated_speed:return 1
        return ((speed-self.cut_in)/(self.rated_speed-self.cut_in))**3
    def simulate(self,timestamp,context):
        if self.config.get("respect_operational_status") and context.get("is_operational") is False:return 0.0
        speed=max(float(context.get("wind_speed_m_s") or 0),0)
        density=context.get("air_density_kg_m3")
        if density is not None:speed*=max(float(density),.1)**(1/3)/self.reference_air_density**(1/3)
        power=self.rated_power*self._fraction(speed)
        limit=context.get("power_limit_kw")
        return min(power,max(float(limit),0)) if limit is not None else power

class EvChargingLoadModel(HourlyDeviceModel):
    def __init__(self,config):
        self.config=config;self.count=max(int(config.get("charger_count",0)),0);self.rated=max(float(config.get("rated_power_kw_per_charger",0)),0);self.util=max(min(float(config.get("utilization_rate",1)),1),0);self.daily=max(float(config.get("daily_energy_kwh",0)),0)
        self.start=int(config.get("charging_start_hour",config.get("arrival_hour",0)))%24;self.end=int(config.get("charging_end_hour",config.get("departure_hour",24)))%24
        raw=config.get("load_curve")
        self.curve=[max(float(v),0) for v in raw] if raw is not None else None
        if self.curve is not None and len(self.curve)!=24:raise ValueError("EV load_curve must contain 24 values")
    def _active_hours(self):
        if self.start==self.end:return list(range(24))
        return list(range(self.start,self.end)) if self.start<self.end else list(range(self.start,24))+list(range(0,self.end))
    def simulate(self,timestamp,context):
        max_power=self.count*self.rated*self.util
        if self.curve is not None:
            total=sum(self.curve);requested=(self.daily*self.curve[timestamp.hour]/total if total and self.daily else max_power*self.curve[timestamp.hour]);return min(requested,max_power)
        hours=self._active_hours()
        if timestamp.hour not in hours:return 0
        requested=self.daily/len(hours) if self.daily else max_power
        return min(requested,max_power)

HourlyDeviceModelRegistry.register("WIND",WindGenerationModel)
HourlyDeviceModelRegistry.register("EV_CHARGER",EvChargingLoadModel)
