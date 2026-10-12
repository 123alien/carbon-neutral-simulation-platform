"""Prepare a traceable 14-day PVDAQ System 35 slice without imputation."""
from __future__ import annotations
import csv,hashlib,json,math,sys
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'real_public_datasets'/'pvdaq_system35';RAW=BASE/'raw';CLEAN=BASE/'cleaned';NORMAL=BASE/'normalized'
sys.path.insert(0,str(ROOT));from app.simulation.solar import SolarInput,SolarIrradianceModel

def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def scores(frame,simulated='simulated_ac_power_kw'):
 x=frame.dropna(subset=['ac_power_kw',simulated]);o=x.ac_power_kw.to_numpy();s=x[simulated].to_numpy();e=s-o
 mae=float(abs(e).mean());rmse=float(math.sqrt((e*e).mean()));obs_energy=float(o.sum()*.25);sim_energy=float(s.sum()*.25)
 return {'paired_records':len(x),'observed_energy_kwh':obs_energy,'simulated_energy_kwh':sim_energy,'mae_kw':mae,'rmse_kw':rmse,'nrmse_pct_of_dc_capacity':rmse/121.68*100,'energy_error_pct':(sim_energy-obs_energy)/obs_energy*100,'correlation':float(pd.Series(o).corr(pd.Series(s)))}
def main():
 CLEAN.mkdir(parents=True,exist_ok=True);NORMAL.mkdir(parents=True,exist_ok=True)
 files=sorted(RAW.glob('system_35__date_*.csv'));df=pd.concat([pd.read_csv(p) for p in files],ignore_index=True)
 local=pd.to_datetime(df.measured_on).dt.tz_localize(ZoneInfo('America/Los_Angeles'),ambiguous='raise',nonexistent='raise');df['timestamp']=local.dt.tz_convert('UTC')
 # Apply the publisher's metric scale/offset metadata exactly; power raw values are hundreds of watts.
 df['poa_irradiance_w_m2']=df.poa_irradiance__2699
 df['ambient_temperature_c']=df.ambient_temp_f__2706*(5/9)-17.77777777777778
 df['module_temperature_c']=df.module_temp_f__2707*(5/9)-17.77777777777778
 df['ac_power_kw']=df.ac_power_hw__2713*100/1000
 df['dc_power_kw']=df.dc_power_hw__2712*100/1000
 legacy=SolarIrradianceModel({'irradiance_mode':'POA','performance_ratio':.85,'inverter_efficiency':1.0,'noct_c':45.0,'temperature_coefficient_per_c':-.004})
 df['simulated_ac_power_kw_legacy']=[legacy.ac_power_kw(SolarInput(0,float(a) if pd.notna(a) else None,float(i) if pd.notna(i) else None),121.68) if pd.notna(i) else None for i,a in zip(df.poa_irradiance_w_m2,df.ambient_temperature_c)]
 base=SolarIrradianceModel({'irradiance_mode':'POA','performance_ratio':1.0,'inverter_efficiency':.96,'temperature_coefficient_per_c':-.004})
 df['_base_ac_power_kw']=[base.ac_power_kw(SolarInput(0,float(a) if pd.notna(a) else None,float(i) if pd.notna(i) else None,float(m) if pd.notna(m) else None),121.68) if pd.notna(i) else None for i,a,m in zip(df.poa_irradiance_w_m2,df.ambient_temperature_c,df.module_temperature_c)]
 split=df.timestamp.min()+timedelta(days=7);train=df[df.timestamp<split].dropna(subset=['ac_power_kw','_base_ac_power_kw']);calibrated_pr=float((train.ac_power_kw.sum()/train._base_ac_power_kw.sum()).clip(.1,1.2))
 improved=SolarIrradianceModel({'irradiance_mode':'POA','performance_ratio':calibrated_pr,'inverter_efficiency':.96,'temperature_coefficient_per_c':-.004})
 df['simulated_ac_power_kw']=[improved.ac_power_kw(SolarInput(0,float(a) if pd.notna(a) else None,float(i) if pd.notna(i) else None,float(m) if pd.notna(m) else None),121.68) if pd.notna(i) else None for i,a,m in zip(df.poa_irradiance_w_m2,df.ambient_temperature_c,df.module_temperature_c)]
 cols=['timestamp','system_id','poa_irradiance_w_m2','ambient_temperature_c','module_temperature_c','dc_power_kw','ac_power_kw','simulated_ac_power_kw_legacy','simulated_ac_power_kw','inverter_error_code__2708'];df[cols].to_csv(CLEAN/'pvdaq35_cleaned.csv',index=False)
 pd.DataFrame([{'external_id':'PVDAQ-35','name':'PVDAQ System 35','device_type':'PV','manufacturer':'Sharp / Satcon','model':'Sharp NU-U240F1 + Satcon 135kW','installed_capacity_kwp':121.68,'module_power_w':240,'module_count':507,'inverter_capacity_kw':135,'azimuth_deg':270,'tilt_deg':'','latitude':36.1952,'longitude':-115.1582,'data_class':'REAL_PUBLIC'}]).to_csv(NORMAL/'devices.csv',index=False)
 metrics=[('poa_irradiance_w_m2','W/m2'),('ambient_temperature_c','C'),('module_temperature_c','C'),('dc_power_kw','kW'),('ac_power_kw','kW')]
 pd.DataFrame([{'code':f'MP-PVDAQ35-{m.upper()}','name':f'PVDAQ 35 {m}','device_external_id':'PVDAQ-35','metric_type':m,'energy_type':'PV','unit':u,'data_class':'REAL_PUBLIC'} for m,u in metrics]).to_csv(NORMAL/'metering_points.csv',index=False)
 with (NORMAL/'pv_metrics.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=['device_external_id','device_name','device_type','timestamp','metric_name','value','unit','source_record_id','data_class']);w.writeheader()
  for _,r in df.iterrows():
   stamp=r.timestamp.isoformat().replace('+00:00','Z');rid=f"PVDAQ-35:{stamp}"
   for m,u in metrics:
    if pd.notna(r[m]):w.writerow({'device_external_id':'PVDAQ-35','device_name':'PVDAQ System 35','device_type':'PV','timestamp':stamp,'metric_name':m,'value':r[m],'unit':u,'source_record_id':rid,'data_class':'REAL_PUBLIC'})
 expected=14*96;missing={m:int(df[m].isna().sum()) for m,_ in metrics};holdout=df[df.timestamp>=split];q={'dataset':'NREL PVDAQ System 35','doi':'10.25984/1846021','data_class':'REAL_PUBLIC','systems':1,'time_range':{'start':df.timestamp.min().isoformat(),'end':df.timestamp.max().isoformat()},'cadence_minutes':15,'theoretical_records':expected,'actual_records':len(df),'completeness':len(df)/expected,'duplicate_timestamps':int(df.timestamp.duplicated().sum()),'missing':missing,'negative_irradiance':int((df.poa_irradiance_w_m2<0).sum()),'negative_ac_power':int((df.ac_power_kw<0).sum()),'irradiance_range_w_m2':[float(df.poa_irradiance_w_m2.min()),float(df.poa_irradiance_w_m2.max())],'ac_power_range_kw':[float(df.ac_power_kw.min()),float(df.ac_power_kw.max())],'model_parameters':{'installed_capacity_kwp':{'value':121.68,'class':'REAL_METADATA'},'module_power_w':{'value':240,'class':'REAL_METADATA'},'module_count':{'value':507,'class':'REAL_METADATA'},'azimuth_deg':{'value':270,'class':'REAL_METADATA'},'inverter_capacity_kw':{'value':135,'class':'REAL_METADATA'},'measured_module_temperature':{'value':True,'class':'REAL_METADATA'},'tilt_deg':{'value':None,'class':'MODEL_DEFAULT_NOT_USED_IN_POA_MODE'},'performance_ratio':{'value':calibrated_pr,'class':'CALIBRATED','training_range':f"{df.timestamp.min().isoformat()} / {split.isoformat()}"},'inverter_efficiency':{'value':.96,'class':'MODEL_DEFAULT'},'temperature_coefficient_per_c':{'value':-.004,'class':'MODEL_DEFAULT'}},'comparison':{'legacy_all_records':scores(df,'simulated_ac_power_kw_legacy'),'controlled_holdout':{'range':f"{split.isoformat()} / {df.timestamp.max().isoformat()}",'before':scores(holdout,'simulated_ac_power_kw_legacy'),'after':scores(holdout,'simulated_ac_power_kw')}},'raw_files':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(RAW.iterdir())],'transformations':['local timestamps interpreted in publisher site timezone America/Los_Angeles then represented in UTC','publisher metric scale/offset applied','measured module temperature preferred over NOCT estimate','calibration uses first 7 days only; metrics compare on untouched second 7-day holdout','power remains kW; energy is integrated as kW × 0.25 h','no interpolation, imputation, timestamp shifting, or synthetic measurements','observed DC, observed AC, and simulated AC remain distinct']}
 (BASE/'manifest.json').write_text(json.dumps(q,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(q['comparison'],indent=2))
if __name__=='__main__':main()
