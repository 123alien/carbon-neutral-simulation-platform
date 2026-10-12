from __future__ import annotations
import csv,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]/"real_public_datasets"

def _read_json(path):return json.loads(path.read_text(encoding="utf-8"))
def _series(path,start,observed,legacy,improved,stride):
    rows=[]
    with path.open(encoding="utf-8-sig") as stream:
        for index,row in enumerate(csv.DictReader(stream)):
            if row["timestamp"]<start or index%stride:continue
            if not row.get(observed) or not row.get(improved):continue
            rows.append({"timestamp":row["timestamp"],"observed_power_kw":float(row[observed]),"legacy_simulated_power_kw":float(row[legacy]),"simulated_power_kw":float(row[improved])})
    return rows

def detail(model:str):
    key=model.upper()
    if key=="WIND":
        manifest=_read_json(ROOT/"kelmarsh_wind"/"manifest.json");controlled=manifest["comparison"]["controlled_holdout"];metrics=controlled["all_records"]
        return {"model":"WIND","model_version":"WindGenerationModel/V2","dataset":manifest["dataset"],"data_class":manifest["data_class"],"time_range":controlled["range"],"metrics":metrics,"parameter_sources":manifest["model_parameters"],"fallback_used":True,"fallback_code":"MODEL_PARAMETER_FALLBACK","limitations":["MM92 manufacturer curve is unavailable in publisher metadata","curve is calibrated on the first 7 days and evaluated on the untouched second 7 days","air-density correction is supported but not applied without pressure observations","status events are displayed but inconsistent Stop intervals do not force measured production to zero"],"series":_series(ROOT/"kelmarsh_wind"/"cleaned"/"kelmarsh_scada_cleaned.csv",controlled["range"].split(" / ")[0],"active_power_kw","simulated_power_kw_legacy","simulated_power_kw",6)}
    if key=="PV":
        manifest=_read_json(ROOT/"pvdaq_system35"/"manifest.json");controlled=manifest["comparison"]["controlled_holdout"]
        return {"model":"PV","model_version":"SolarIrradianceModel/V2","dataset":manifest["dataset"],"data_class":manifest["data_class"],"time_range":controlled["range"],"metrics":{"before":controlled["before"],"after":controlled["after"]},"parameter_sources":manifest["model_parameters"],"fallback_used":True,"fallback_code":"MODEL_PARAMETER_FALLBACK","limitations":["performance ratio is calibrated on the first 7 days and is not real device metadata","inverter efficiency and temperature coefficient remain model defaults","measured module temperature is used when present"],"series":_series(ROOT/"pvdaq_system35"/"cleaned"/"pvdaq35_cleaned.csv",controlled["range"].split(" / ")[0],"ac_power_kw","simulated_ac_power_kw_legacy","simulated_ac_power_kw",4)}
    raise LookupError("model validation not found")

def summaries():
    items=[]
    for model in ("WIND","PV"):
        try:
            items.append({k:v for k,v in detail(model).items() if k!="series"})
        except FileNotFoundError:
            # Public validation datasets are optional runtime assets. Their
            # removal must not prevent a park report from being generated,
            # and absence must never be represented as a successful result.
            items.append({
                "model":model,
                "status":"NOT_AVAILABLE",
                "data_class":None,
                "fallback_used":None,
                "limitations":["模型验证数据集未安装，当前报告不包含该模型的实测对比结论"],
            })
    return items
