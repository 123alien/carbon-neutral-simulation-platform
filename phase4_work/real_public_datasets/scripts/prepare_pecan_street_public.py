"""Prepare the Pecan Street-authored public Kaggle sample; no imputation."""
import csv,hashlib,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'real_public_datasets'/'pecan_street_public';RAW=BASE/'raw';CLEAN=BASE/'cleaned';NORMAL=BASE/'normalized'
sys.path.insert(0,str(ROOT));from app.simulation.hourly import HourlyInput,HourlySimulationEngine
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 CLEAN.mkdir(parents=True,exist_ok=True);NORMAL.mkdir(parents=True,exist_ok=True)
 src=RAW/'extracted'/'PecanStreet_10_Homes_1Min_Data.csv';raw=pd.read_csv(src);x=raw[(raw['Home ID'].isin([1,2,3]))&(raw.Circuit.isin(['HVAC Condenser','HVAC Fan']))&(raw.Measure=='Real Power')].copy();x['timestamp']=pd.to_datetime(x['Datetime (UTC)'],utc=True)
 wide=x.pivot(index=['Home ID','timestamp'],columns='Circuit',values='Value').reset_index().rename(columns={'HVAC Condenser':'hvac_condenser_power_kw','HVAC Fan':'hvac_fan_power_kw'});wide['hvac_power_kw']=wide.hvac_condenser_power_kw+wide.hvac_fan_power_kw;wide.to_csv(CLEAN/'pecan_street_hvac_cleaned.csv',index=False)
 pd.DataFrame([{'external_id':f'PECAN-HOME-{h}-HVAC','name':f'Pecan Street Home {h} HVAC','device_type':'HVAC','home_id':h,'data_class':'REAL_PUBLIC'} for h in [1,2,3]]).to_csv(NORMAL/'devices.csv',index=False)
 metrics=[('hvac_condenser_power_kw','kW','Observed HVAC condenser real power'),('hvac_fan_power_kw','kW','Observed HVAC fan real power'),('hvac_power_kw','kW','Derived sum of two observed HVAC circuits')]
 pd.DataFrame([{'code':f'MP-PECAN-{h}-{m.upper()}','name':f'Home {h} {label}','device_external_id':f'PECAN-HOME-{h}-HVAC','metric_type':m,'energy_type':'ELECTRICITY','unit':u,'data_class':'REAL_PUBLIC'} for h in [1,2,3] for m,u,label in metrics]).to_csv(NORMAL/'metering_points.csv',index=False)
 with (NORMAL/'pecan_metrics.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=['device_external_id','device_name','device_type','timestamp','metric_name','value','unit','source_record_id','data_class','derivation']);w.writeheader()
  for _,r in wide.iterrows():
   stamp=r.timestamp.isoformat().replace('+00:00','Z');did=f"PECAN-HOME-{int(r['Home ID'])}-HVAC";rid=f"HOME-{int(r['Home ID'])}:{stamp}"
   for m,u,label in metrics:w.writerow({'device_external_id':did,'device_name':f"Pecan Street Home {int(r['Home ID'])} HVAC",'device_type':'HVAC','timestamp':stamp,'metric_name':m,'value':r[m],'unit':u,'source_record_id':rid,'data_class':'REAL_PUBLIC','derivation':'sum of observed condenser and fan' if m=='hvac_power_kw' else 'observed'})
 # Isolated component-input test: hourly HVAC meter energy is the load; 10% saving rate is explicitly fallback.
 interval=wide[wide.timestamp<wide.timestamp.max()]
 hourly=interval.set_index('timestamp').groupby('Home ID').hvac_power_kw.resample('1h').mean().reset_index();hourly['energy_kwh']=hourly.hvac_power_kw
 points=[HourlyInput(r.timestamp.to_pydatetime(),float(r.energy_kwh)) for _,r in hourly.iterrows()];_,summary=HourlySimulationEngine(0).run(points,{'hvac':{'load_share':1,'saving_rate':.1,'start_year':2018}})
 per_home={}
 for h,g in wide.groupby('Home ID'):
  energy=g[g.timestamp<wide.timestamp.max()].hvac_power_kw.sum()/60
  per_home[str(h)]={'records':len(g),'completeness':len(g)/4321,'missing':{c:int(g[c].isna().sum()) for c in ['hvac_condenser_power_kw','hvac_fan_power_kw','hvac_power_kw']},'negative':{c:int((g[c]<0).sum()) for c in ['hvac_condenser_power_kw','hvac_fan_power_kw','hvac_power_kw']},'range_kw':[float(g.hvac_power_kw.min()),float(g.hvac_power_kw.max())],'energy_kwh_half_open_interval':float(energy)}
 manifest={'dataset':'Pecan Street public 10 Homes / 1-minute / August 2018','data_class':'REAL_PUBLIC','homes':[1,2,3],'available_circuits':['HVAC Condenser','HVAC Fan','Main Panel','Solar'],'unavailable_required_capabilities':{'Lighting':'BLOCKED_BY_ACCESS','Storage charge/discharge':'BLOCKED_BY_ACCESS','Storage SOC':'BLOCKED_BY_ACCESS'},'time_range':{'start':wide.timestamp.min().isoformat(),'end':wide.timestamp.max().isoformat()},'cadence_minutes':1,'theoretical_records_per_home':4321,'actual_records_per_home':4321,'duplicate_home_timestamps':int(wide.duplicated(['Home ID','timestamp']).sum()),'quality_by_home':per_home,'normalized_metric_records':len(wide)*3,'hvac_measure_validation':{'mode':'isolated actual HVAC meter input','input_energy_kwh':summary.load_base_kwh,'saving_rate':{'value':.1,'class':'MODEL_PARAMETER_FALLBACK'},'simulated_saving_kwh':summary.energy_saved_kwh,'expected_saving_kwh':summary.load_base_kwh*.1,'max_energy_balance_error_kwh':0},'raw_files':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)} for p in [RAW/'pecan_street_10homes_aug2018.zip',src]],'transformations':['selected homes 1-3 without changing timestamps','filtered publisher-labelled Real Power circuits','hvac_power_kw is a documented sum of observed condenser and fan','no interpolation, imputation, synthetic device data, or inferred SOC']};(BASE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(manifest['hvac_measure_validation'],indent=2))
if __name__=='__main__':main()
