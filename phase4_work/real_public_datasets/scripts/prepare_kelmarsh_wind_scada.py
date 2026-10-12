"""Prepare one auditable Kelmarsh SCADA slice without altering observations."""
from __future__ import annotations

import csv, hashlib, json, math, statistics, sys, zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.simulation.device_models import WindGenerationModel
BASE=ROOT/"real_public_datasets"/"kelmarsh_wind"
RAW=BASE/"raw";CLEANED=BASE/"cleaned";NORMALIZED=BASE/"normalized"
ARCHIVE=RAW/"Kelmarsh_SCADA_2016_3082.zip";TURBINES=(1,2,3);DAYS=14
FIELDS={"Wind speed (m/s)":"wind_speed_m_s","Power (kW)":"active_power_kw","Wind direction (°)":"wind_direction_deg","Rotor speed (RPM)":"rotor_speed_rpm","Nacelle ambient temperature (°C)":"temperature_c","Turbine Power setpoint (kW)":"power_setpoint_kw"}
UNITS={"wind_speed_m_s":"m/s","active_power_kw":"kW","wind_direction_deg":"deg","rotor_speed_rpm":"rpm","temperature_c":"C","power_setpoint_kw":"kW"}

def digest(path,algorithm="sha256"):
    h=hashlib.new(algorithm)
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()
def parse(value):return datetime.strptime(value,"%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
def number(value):
    try:
        result=float(value);return result if math.isfinite(result) else None
    except (TypeError,ValueError):return None
def reader(entry):
    stream=(line.decode("utf-8-sig") for line in entry if not line.startswith(b"#") or line.startswith(b"# Date and time"))
    return csv.DictReader(stream)
LEGACY_MODEL=WindGenerationModel({"rated_power_kw":2050,"cut_in_speed_m_s":3,"rated_speed_m_s":12,"cut_out_speed_m_s":25,"curve_mode":"SIMPLE_CURVE"})
def scores(rows,simulated="simulated_power_kw"):
    pairs=[(r["active_power_kw"],r[simulated]) for r in rows if r["active_power_kw"] is not None and r["wind_speed_m_s"] is not None and r.get(simulated) is not None]
    errors=[s-o for o,s in pairs];mae=sum(abs(x) for x in errors)/len(errors);rmse=math.sqrt(sum(x*x for x in errors)/len(errors));oe=sum(o for o,_ in pairs)/6;se=sum(s for _,s in pairs)/6
    corr=statistics.correlation([x[0] for x in pairs],[x[1] for x in pairs]) if len(pairs)>1 else None
    return {"points":len(pairs),"observed_energy_kwh":oe,"simulated_energy_kwh":se,"mae_kw":mae,"rmse_kw":rmse,"nrmse_pct_rated":rmse/2050*100,"energy_error_pct":(se-oe)/oe*100 if oe else None,"correlation":corr}

def main():
    CLEANED.mkdir(parents=True,exist_ok=True);NORMALIZED.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(ARCHIVE) as z:
        all_rows={};events={}
        for turbine in TURBINES:
            data_name=next(x for x in z.namelist() if x.startswith(f"Turbine_Data_Kelmarsh_{turbine}_"));status_name=next(x for x in z.namelist() if x.startswith(f"Status_Kelmarsh_{turbine}_"))
            with z.open(data_name) as f:
                all_rows[turbine]=[{"timestamp":parse(row["# Date and time"]),**{target:number(row.get(source)) for source,target in FIELDS.items()}} for row in reader(f)]
            with z.open(status_name) as f:
                events[turbine]=[{**row,"start":parse(row["Timestamp start"]),"end":parse(row["Timestamp end"]) if row["Timestamp end"] not in {"","-"} else datetime(2100,1,1,tzinfo=timezone.utc)} for row in reader(f) if row["Timestamp start"] not in {"","-"}]
    # Select the best complete 14-day window after the official commercial operation date.
    lookup={t:{r["timestamp"]:r for r in rows} for t,rows in all_rows.items()};start=datetime(2016,4,15,tzinfo=timezone.utc);last=datetime(2016,12,18,tzinfo=timezone.utc);best=None
    while start<=last:
        stamps=[start+timedelta(minutes=10*i) for i in range(DAYS*144)];complete=sum(lookup[t].get(s,{}).get("wind_speed_m_s") is not None and lookup[t].get(s,{}).get("active_power_kw") is not None for t in TURBINES for s in stamps)
        candidate=(complete,start)
        if best is None or candidate>best:best=candidate
        start+=timedelta(days=1)
    _,window_start=best;window_end=window_start+timedelta(days=DAYS);selected=[]
    for turbine in TURBINES:
        active=events[turbine]
        for row in all_rows[turbine]:
            if not window_start<=row["timestamp"]<window_end:continue
            matching=[x for x in active if x["start"]<=row["timestamp"]<x["end"]]
            event=matching[0] if matching else None
            row.update({"turbine_id":f"KELMARSH-{turbine}","status":event.get("Status") if event else "NO_ACTIVE_EVENT","status_code":event.get("Code") if event else "","status_message":event.get("Message") if event else "","non_running":bool(event and event.get("Status","").lower()=="stop"),"simulated_power_kw_legacy":LEGACY_MODEL.simulate(row["timestamp"],{"wind_speed_m_s":row["wind_speed_m_s"]}) if row["wind_speed_m_s"] is not None else None})
            selected.append(row)
    selected.sort(key=lambda x:(x["timestamp"],x["turbine_id"]))
    split=window_start+timedelta(days=7);training=[r for r in selected if r["timestamp"]<split and not r["non_running"] and r["wind_speed_m_s"] is not None and r["active_power_kw"] is not None and r["active_power_kw"]>=0]
    bins=defaultdict(list)
    for r in training:bins[round(r["wind_speed_m_s"]*2)/2].append(min(max(r["active_power_kw"]/2050,0),1))
    curve=[];last=0.0
    for speed in sorted(x for x in bins if 3<=x<25):
        fraction=max(last,statistics.median(bins[speed]));last=min(fraction,1.0);curve.append({"wind_speed_m_s":speed,"power_fraction":last})
    calibrated=WindGenerationModel({"rated_power_kw":2050,"cut_in_speed_m_s":3,"rated_speed_m_s":12,"cut_out_speed_m_s":25,"curve_mode":"CALIBRATED_CURVE","power_curve":curve,"respect_operational_status":False})
    for row in selected:row["simulated_power_kw"]=calibrated.simulate(row["timestamp"],{"wind_speed_m_s":row["wind_speed_m_s"],"is_operational":not row["non_running"],"power_limit_kw":row["power_setpoint_kw"]}) if row["wind_speed_m_s"] is not None else None
    clean_fields=["timestamp","turbine_id",*FIELDS.values(),"status","status_code","status_message","non_running","simulated_power_kw_legacy","simulated_power_kw"]
    with (CLEANED/"kelmarsh_scada_cleaned.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=clean_fields);w.writeheader()
        for row in selected:w.writerow({**row,"timestamp":row["timestamp"].isoformat().replace("+00:00","Z")})
    static=list(csv.DictReader((RAW/"Kelmarsh_WT_static.csv").open(encoding="utf-8-sig")))[:3]
    devices=[{"external_id":f"KELMARSH-{i}","code":f"KELMARSH-{i}","name":x["Title"],"device_type":"WIND","manufacturer":x["Manufacturer"],"model":x["Model"],"rated_power_kw":x["Rated power (kW)"],"hub_height_m":x["Hub Height (m)"],"rotor_diameter_m":x["Rotor Diameter (m)"],"latitude":x["Latitude"],"longitude":x["Longitude"],"data_class":"REAL_PUBLIC"} for i,x in enumerate(static,1)]
    with (NORMALIZED/"devices.csv").open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=devices[0]);w.writeheader();w.writerows(devices)
    points=[]
    for t in TURBINES:
        for metric in FIELDS.values():points.append({"code":f"MP-KEL-{t}-{metric.upper()}","name":f"Kelmarsh {t} {metric}","device_external_id":f"KELMARSH-{t}","metric_type":metric,"energy_type":"WIND","unit":UNITS[metric],"data_class":"REAL_PUBLIC"})
    with (NORMALIZED/"metering_points.csv").open("w",encoding="utf-8-sig",newline="") as f:w=csv.DictWriter(f,fieldnames=points[0]);w.writeheader();w.writerows(points)
    metric_fields=["device_external_id","device_name","device_type","timestamp","metric_name","value","unit","source_record_id","turbine_status","status_code","status_message","data_class"]
    with (NORMALIZED/"wind_metrics.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=metric_fields);w.writeheader()
        for row in selected:
            for metric in FIELDS.values():
                if row[metric] is not None:w.writerow({"device_external_id":row["turbine_id"],"device_name":row["turbine_id"].replace("KELMARSH-","Kelmarsh "),"device_type":"WIND","timestamp":row["timestamp"].isoformat().replace("+00:00","Z"),"metric_name":metric,"value":row[metric],"unit":UNITS[metric],"source_record_id":f"{row['turbine_id']}:{row['timestamp'].isoformat()}","turbine_status":row["status"],"status_code":row["status_code"],"status_message":row["status_message"],"data_class":"REAL_PUBLIC"})
    theoretical=DAYS*144*len(TURBINES);actual=len(selected);metric_missing={m:sum(r[m] is None for r in selected) for m in FIELDS.values()};duplicates=actual-len({(r["turbine_id"],r["timestamp"]) for r in selected})
    comparable=[r for r in selected if r["wind_speed_m_s"] is not None and r["active_power_kw"] is not None];normal=[r for r in comparable if not r["non_running"]];holdout=[r for r in comparable if r["timestamp"]>=split];holdout_normal=[r for r in holdout if not r["non_running"]]
    quality={"dataset":"Kelmarsh Wind Farm SCADA","doi":"10.5281/zenodo.8252025","license":"CC BY 4.0","data_class":"REAL_PUBLIC","turbines":list(TURBINES),"time_range":{"start":window_start.isoformat(),"end_exclusive":window_end.isoformat()},"cadence_minutes":10,"theoretical_records":theoretical,"actual_records":actual,"completeness":actual/theoretical,"duplicate_timestamps":duplicates,"missing":metric_missing,"negative_wind_speed":sum((r["wind_speed_m_s"] or 0)<0 for r in selected),"negative_active_power":sum(r["active_power_kw"] is not None and r["active_power_kw"]<0 for r in selected),"wind_speed_range":[min(r["wind_speed_m_s"] for r in selected if r["wind_speed_m_s"] is not None),max(r["wind_speed_m_s"] for r in selected if r["wind_speed_m_s"] is not None)],"active_power_range_kw":[min(r["active_power_kw"] for r in selected if r["active_power_kw"] is not None),max(r["active_power_kw"] for r in selected if r["active_power_kw"] is not None)],"non_running_records":sum(r["non_running"] for r in selected),"model_parameters":{"rated_power_kw":{"value":2050,"source":"Kelmarsh_WT_static.csv","class":"REAL_METADATA"},"hub_height_m":{"values":[78.5,78.5,68.5],"source":"Kelmarsh_WT_static.csv","class":"REAL_METADATA"},"rotor_diameter_m":{"value":92,"source":"Kelmarsh_WT_static.csv","class":"REAL_METADATA"},"curve_mode":{"value":"CALIBRATED_CURVE","class":"CALIBRATED","training_range":f"{window_start.isoformat()} / {split.isoformat()}","points":curve},"manufacturer_curve":{"value":None,"class":"MODEL_PARAMETER_FALLBACK","reason":"no reliable MM92 manufacturer curve found in publisher metadata"},"air_density":{"value":None,"class":"MODEL_PARAMETER_FALLBACK","reason":"SCADA slice has no pressure measurement; correction supported but not applied"},"status_control":{"value":"DISPLAY_ONLY","class":"REAL_METADATA","reason":"published Stop intervals overlap substantial positive observed power; not safe as shutdown command"},"cut_in_speed_m_s":{"value":3,"class":"MODEL_PARAMETER_FALLBACK"},"rated_speed_m_s":{"value":12,"class":"MODEL_PARAMETER_FALLBACK"},"cut_out_speed_m_s":{"value":25,"class":"MODEL_PARAMETER_FALLBACK"}},"comparison":{"legacy_all_records":scores(comparable,"simulated_power_kw_legacy"),"controlled_holdout":{"range":f"{split.isoformat()} / {window_end.isoformat()}","all_records":{"before":scores(holdout,"simulated_power_kw_legacy"),"after":scores(holdout)},"excluding_active_stop_intervals":{"before":scores(holdout_normal,"simulated_power_kw_legacy"),"after":scores(holdout_normal)}},"normal_filter":"exclude timestamps covered by a published Status=Stop interval; observations are not deleted"},"transformations":["selected the most complete continuous 14-day post-commercial-operation window","timestamps unchanged and explicitly UTC","calibrated curve uses first 7 days only; comparison uses untouched second 7-day holdout","power setpoint is applied only as an observed operational upper limit","status/event intervals preserved and displayed but not used to force zero due observed inconsistency","air-density correction supported but not applied without pressure data","no interpolation, imputation, year shifting or synthetic values","simulated_power_kw is separate from observed active_power_kw"]}
    outputs=[]
    for path in [CLEANED/"kelmarsh_scada_cleaned.csv",*NORMALIZED.glob("*.csv")]:outputs.append({"path":str(path.relative_to(ROOT)).replace("\\","/"),"sha256":digest(path),"bytes":path.stat().st_size})
    quality["raw_files"]=[{"path":str(ARCHIVE.relative_to(ROOT)).replace("\\","/"),"sha256":digest(ARCHIVE),"md5":digest(ARCHIVE,"md5"),"bytes":ARCHIVE.stat().st_size},{"path":str((RAW/"Kelmarsh_WT_static.csv").relative_to(ROOT)).replace("\\","/"),"sha256":digest(RAW/"Kelmarsh_WT_static.csv")},{"path":str((RAW/"Kelmarsh_WT_dataSignalMapping.csv").relative_to(ROOT)).replace("\\","/"),"sha256":digest(RAW/"Kelmarsh_WT_dataSignalMapping.csv")}];quality["outputs"]=outputs
    (BASE/"manifest.json").write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__":main()
