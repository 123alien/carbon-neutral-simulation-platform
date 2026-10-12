from itertools import combinations
from app.simulation.green_power import GreenPowerAllocator
from app.simulation.hourly import HourlySimulationEngine
from app.recommendation.measure_catalog import p4_experiment_candidates,validate_measure_parameters

DEFAULT_WEIGHTS={
    "ECONOMIC":{"reduction":.15,"investment":.30,"payback":.30,"applicability":.15,"target":.10},
    "REDUCTION":{"reduction":.40,"investment":.10,"payback":.10,"applicability":.15,"target":.25},
    "BALANCED":{"reduction":.25,"investment":.20,"payback":.20,"applicability":.15,"target":.20},
}

class LowCarbonPathRecommendationEngine:
    def __init__(self,points,electricity_factor,electricity_price=.57,feed_in_tariff=.42):
        self.points=points;self.factor=electricity_factor;self.price=electricity_price;self.tariff=feed_in_tariff

    def _library(self,context,overrides):
        peak=max((point.load_kwh for point in self.points),default=0);area=float(context.get("building_area") or 0);population=float(context.get("population") or 0);avg_wind=sum(float(point.wind_speed_m_s or 0) for point in self.points)/len(self.points);avg_ghi=sum(float(point.irradiation_wm2 or 0) for point in self.points)/len(self.points)
        defaults={
            "PV":({"capacity_kw":max(peak*.6,10),"performance_ratio":.82,"inverter_efficiency":.97,"degradation_rate":.007,"start_year":context["year"]},max(peak*.6,10)*4000,.9 if avg_ghi>50 else .3),
            "WIND":({"rated_power_kw":max(peak*.3,5),"cut_in_speed_m_s":3,"rated_speed_m_s":12,"cut_out_speed_m_s":25,"start_year":context["year"]},max(peak*.3,5)*8000,.9 if avg_wind>=5 else .25),
            "STORAGE":({"capacity_kwh":max(peak*2,10),"max_charge_kw":max(peak*.5,5),"max_discharge_kw":max(peak*.5,5),"charge_efficiency":.95,"discharge_efficiency":.95,"soc_initial":.5,"soc_min":.1,"soc_max":.9,"strategy":"PV_SELF_CONSUMPTION","start_year":context["year"]},max(peak*2,10)*1500,.75),
            "HVAC":({"load_share":.4,"saving_rate":.2,"start_year":context["year"]},max(area*35,20000),.9 if area else .6),
            "LIGHTING":({"load_share":.2,"saving_rate":.5,"start_year":context["year"]},max(area*12,10000),.95 if area else .7),
            "EV_CHARGER":({"charger_count":max(round(population/100),1),"rated_power_kw_per_charger":7,"utilization_rate":.25,"daily_energy_kwh":max(population*.05,10),"charging_start_hour":22,"charging_end_hour":7,"start_year":context["year"]},max(round(population/100),1)*8000,.7 if population else .4),
            "GREEN_POWER":({"purchase_share":.3,"emission_factor_kg_per_kwh":0,"premium_per_kwh":.05,"start_year":context["year"]},0,1),
        }
        audited = p4_experiment_candidates("MEDIUM") if context.get("baseline_scenario_version_id") == 3 else None
        if audited:
            for name,item in audited.items():
                if not item["enabled"]:
                    defaults.pop(name,None);continue
                params=dict(item["parameters"]);params["start_year"]=context["year"]
                if name=="PV":capex=float(params["capacity_kw"])*4000;applicability=.65
                elif name=="WIND":capex=float(params["rated_power_kw"])*8000;applicability=.35
                elif name=="STORAGE":capex=float(params["capacity_kwh"])*1500;applicability=.7
                elif name=="HVAC":capex=max(area*35,20000);applicability=.5
                elif name=="GREEN_POWER":capex=0;applicability=.7
                else:continue
                defaults[name]=(params,capex,applicability)
        result=[]
        for name,(params,capex,applicability) in defaults.items():
            custom=overrides.get(name,{})
            params={**params,**custom.get("parameters",custom)};capex=float(custom.get("capex",capex)) if isinstance(custom,dict) else capex
            if isinstance(custom,dict) and custom.get("disabled") is True:continue
            validate_measure_parameters(name,params)
            source=(audited or {}).get(name,{})
            result.append({"type":name,"parameters":params,"investment":capex,"applicability":applicability,"parameter_sources":source.get("parameter_sources",{}),"recommendation_status":source.get("recommendation_status","LEGACY_MODEL_DEFAULT")})
        return result

    @staticmethod
    def _config(measures):
        mapping={"PV":"pv","WIND":"wind","STORAGE":"storage","HVAC":"hvac","LIGHTING":"lighting","EV_CHARGER":"ev_charger"}
        return {mapping[item["type"]]:item["parameters"] for item in measures if item["type"] in mapping}

    @staticmethod
    def _green_allocator(measures,start,end):
        green=next((item for item in measures if item["type"]=="GREEN_POWER"),None)
        if not green:return None
        p=green["parameters"]
        return GreenPowerAllocator([{"start_at":start,"end_at":end,"purchase_share":p.get("purchase_share"),"purchase_kwh":p.get("purchase_kwh"),"emission_factor_kg_per_kwh":p.get("emission_factor_kg_per_kwh",0),"premium_per_kwh":p.get("premium_per_kwh",0)}])

    def recommend(self,request,context):
        from app.services.campus_simulation_input import combine
        base=context.get('baseline_config',{})
        simulator=HourlySimulationEngine(self.factor,self.price,self.tariff);_,baseline=simulator.run(self.points,base)
        library=self._library(context,request.candidate_parameters);candidates=[]
        combos=[combo for size in (1,2,3) for combo in combinations(library,size)]
        for combo in combos:
            investment=sum(item["investment"] for item in combo)
            if investment>request.budget:continue
            allocator=self._green_allocator(combo,self.points[0].timestamp,self.points[-1].timestamp.replace(hour=23,minute=59,second=59))
            results,summary=HourlySimulationEngine(self.factor,self.price,self.tariff).run(self.points,combine(base,self._config(combo)),allocator)
            reduction=baseline.carbon_emission_t-summary.carbon_emission_t;baseline_net=baseline.electricity_cost-baseline.feed_in_revenue;candidate_net=summary.electricity_cost-summary.feed_in_revenue;annual_saving=baseline_net-candidate_net
            payback=investment/annual_saving if investment>0 and annual_saving>0 else (0 if investment==0 and annual_saving>=0 else 999)
            reduction_score=max(min(reduction/baseline.carbon_emission_t,1),0) if baseline.carbon_emission_t else 0
            investment_score=max(1-investment/request.budget,0);payback_score=max(1-min(payback/20,1),0);applicability=sum(item["applicability"] for item in combo)/len(combo)
            targets=[]
            if request.carbon_quota_t is not None:targets.append(min(request.carbon_quota_t/summary.carbon_emission_t,1) if summary.carbon_emission_t else 1)
            if request.energy_target_kwh is not None:targets.append(min(request.energy_target_kwh/summary.grid_power_kwh,1) if summary.grid_power_kwh else 1)
            if request.target_neutral_year:targets.append(min(reduction_score*max(request.target_neutral_year-request.simulation_year,1),1))
            if request.target_peak_year:targets.append(1 if reduction>=0 and request.simulation_year<=request.target_peak_year else max(reduction_score,0))
            target=sum(targets)/len(targets) if targets else reduction_score
            reasons=[f"经现有小时仿真引擎验证，预计减排 {reduction:.4g} tCO2",f"预计投资 {investment:.4g}，回收期 {'不可回收' if payback>=999 else f'{payback:.2f} 年'}",f"技术适用性 {applicability:.0%}，目标满足度 {target:.0%}"]
            candidates.append({"measures":[{"type":item["type"],"parameters":item["parameters"],"investment":item["investment"],"parameter_sources":item["parameter_sources"],"recommendation_status":item["recommendation_status"]} for item in combo],"reasons":reasons,"metrics":{"estimated_reduction_t":reduction,"investment":investment,"payback_years":None if payback>=999 else payback,"target_satisfaction":target,"technical_applicability":applicability,"grid_power_kwh":summary.grid_power_kwh,"carbon_emission_t":summary.carbon_emission_t},"dimensions":{"reduction":reduction_score,"investment":investment_score,"payback":payback_score,"applicability":applicability,"target":target},"validation":{"engine":"HourlySimulationEngine","hours":summary.hours,"max_energy_balance_error_kwh":max(abs(row.energy_balance_error_kwh) for row in results),"baseline_carbon_emission_t":baseline.carbon_emission_t,"validated":True}})
        if not candidates:raise ValueError("no candidate path fits the budget")
        profiles={}
        for profile,defaults in DEFAULT_WEIGHTS.items():
            weights={**defaults,**request.weights.get(profile,{})};total=sum(max(value,0) for value in weights.values()) or 1
            ranked=[]
            for candidate in candidates:
                score=sum(candidate["dimensions"][key]*max(weight,0) for key,weight in weights.items())/total;ranked.append(({**candidate,"score":score},score))
            profiles[profile]=[item[0] for item in sorted(ranked,key=lambda pair:pair[1],reverse=True)[:request.top_n]]
        return baseline,profiles
