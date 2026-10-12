"""Preview and, only with --confirm, import Kelmarsh through the formal FILE Adapter."""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"real_public_datasets"/"kelmarsh_wind";NORMALIZED=BASE/"normalized";API="http://127.0.0.1:8000"
def checked(response):
    if not response.is_success:raise RuntimeError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text[:1000]}")
    return response.json()
def rows(name):return list(csv.DictReader((NORMALIZED/name).open(encoding="utf-8-sig")))
def main(confirm=False):
    metrics=rows("wind_metrics.csv");preview={"status":"PREVIEW_ONLY" if not confirm else "CONFIRMED","source_file":str((NORMALIZED/"wind_metrics.csv").resolve()),"record_count":len(metrics),"columns":list(metrics[0]),"sample":metrics[:5],"metric_counts":{m:sum(x["metric_name"]==m for x in metrics) for m in sorted({x["metric_name"] for x in metrics})},"time_range":[min(x["timestamp"] for x in metrics),max(x["timestamp"] for x in metrics)],"writes_performed":False}
    (BASE/"preview.json").write_text(json.dumps(preview,ensure_ascii=False,indent=2),encoding="utf-8")
    if not confirm:print(json.dumps(preview,ensure_ascii=False,indent=2));return
    with httpx.Client(base_url=API,timeout=300,trust_env=False) as client:
        enterprise=next((x for x in checked(client.get("/api/enterprises")) if x["name"]=="Kelmarsh Wind Public Validation"),None) or checked(client.post("/api/enterprises",json={"name":"Kelmarsh Wind Public Validation","region":"UK-England","industry":"Public wind SCADA validation","base_year":2016}))
        org=next((x for x in checked(client.get("/api/organizations",params={"enterprise_id":enterprise["id"]})) if x.get("code")=="KELMARSH-WIND"),None) or checked(client.post("/api/organizations",json={"enterprise_id":enterprise["id"],"name":"Kelmarsh Wind Validation Organization","level":"BUILDING_PARK","code":"KELMARSH-WIND","metadata_json":{"data_class":"REAL_PUBLIC","doi":"10.5281/zenodo.8252025"}}))
        site=next((x for x in checked(client.get("/api/sites",params={"enterprise_id":enterprise["id"]})) if x["code"]=="KELMARSH-WIND"),None) or checked(client.post("/api/sites",json={"enterprise_id":enterprise["id"],"organization_node_id":org["id"],"code":"KELMARSH-WIND","name":"Wind Validation Site · Kelmarsh UK","site_type":"OTHER","address":"Kelmarsh, Northamptonshire, United Kingdom","timezone":"UTC","latitude":52.400604,"longitude":-0.947133,"metadata_json":{"data_class":"REAL_PUBLIC","dataset":"Kelmarsh Wind Farm SCADA","country":"UK","publisher":"Cubico Sustainable Investments Ltd","license":"CC BY 4.0","doi":"10.5281/zenodo.8252025","not_target_china_site":True}}))
        system=next((x for x in checked(client.get("/api/energy-systems",params={"site_id":site["id"]})) if x["code"]=="KELMARSH-WIND-SYSTEM"),None) or checked(client.post("/api/energy-systems",json={"site_id":site["id"],"code":"KELMARSH-WIND-SYSTEM","name":"Kelmarsh Wind EnergySystem","system_type":"WIND","metadata_json":{"data_class":"REAL_PUBLIC","rated_capacity_kw":6150}}))
        source=next((x for x in checked(client.get("/api/data-sources",params={"enterprise_id":enterprise["id"]})) if x["name"]=="Kelmarsh official SCADA FILE"),None) or checked(client.post("/api/data-sources",json={"enterprise_id":enterprise["id"],"name":"Kelmarsh official SCADA FILE","source_type":"FILE","config_json":{"path":str((NORMALIZED/"wind_metrics.csv").resolve()),"timezone":"UTC","source_record_id_path":"source_record_id","data_class":"REAL_PUBLIC","dataset":"Kelmarsh Wind Farm SCADA","doi":"10.5281/zenodo.8252025","license":"CC BY 4.0","preview_file":str((BASE/"preview.json").resolve())}}))
        existing={x["external_id"]:x for x in checked(client.get("/api/devices",params={"enterprise_id":enterprise["id"]}))};devices=[]
        for raw in rows("devices.csv"):
            device=existing.get(raw["external_id"]) or checked(client.post("/api/devices",json={"enterprise_id":enterprise["id"],"data_source_id":source["id"],"external_id":raw["external_id"],"name":raw["name"],"device_type":"WIND","longitude":float(raw["longitude"]),"latitude":float(raw["latitude"]),"metadata_json":{"data_class":"REAL_PUBLIC","manufacturer":raw["manufacturer"],"model":raw["model"],"rated_power_kw":float(raw["rated_power_kw"]),"hub_height_m":float(raw["hub_height_m"]),"rotor_diameter_m":float(raw["rotor_diameter_m"]),"model_parameter_fallback":{"cut_in_speed_m_s":3,"rated_speed_m_s":12,"cut_out_speed_m_s":25}}}));devices.append(device)
        quality_before=checked(client.get(f"/api/data-sources/{source['id']}/data-quality"));sync=checked(client.post(f"/api/data-sources/{source['id']}/sync")) if quality_before["valid_records"]==0 else {"idempotent_resume":True,"inserted":quality_before["valid_records"]}
        existing_points={x["code"]:x for x in checked(client.get("/api/metering-points",params={"site_id":site["id"]}))};device_map={x["external_id"]:x for x in devices};points=[]
        for raw in rows("metering_points.csv"):
            points.append(existing_points.get(raw["code"]) or checked(client.post("/api/metering-points",json={"site_id":site["id"],"energy_system_id":system["id"],"device_id":device_map[raw["device_external_id"]]["id"],"data_source_id":source["id"],"code":raw["code"],"name":raw["name"],"metric_type":raw["metric_type"],"energy_type":"WIND","unit":raw["unit"],"metadata_json":{"data_class":"REAL_PUBLIC","observed":True}})))
        result={"preview":preview,"enterprise":enterprise,"site":site,"energy_system":system,"data_source":source,"devices":devices,"metering_points":points,"sync":sync,"quality":checked(client.get(f"/api/data-sources/{source['id']}/data-quality"))};preview["writes_performed"]=True
    (BASE/"import_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps({"site_id":site["id"],"source_id":source["id"],"sync":sync,"quality":result["quality"]},ensure_ascii=False,indent=2))
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--confirm",action="store_true");main(parser.parse_args().confirm)
