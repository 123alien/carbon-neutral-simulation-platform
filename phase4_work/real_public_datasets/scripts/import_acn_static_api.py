"""Import the authenticated-API-blocked ACN static slice through platform APIs only."""
from __future__ import annotations

import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "real_public_datasets"
NORMALIZED = DATA / "normalized" / "acn_data" / "caltech_garage_01_2018_05_01_14"
API = "http://127.0.0.1:8000"


def checked(response: httpx.Response):
    if not response.is_success:
        raise RuntimeError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text[:1000]}")
    return response.json()


def main() -> None:
    with httpx.Client(base_url=API, timeout=300, trust_env=False) as client:
        enterprise = next((x for x in checked(client.get("/api/enterprises")) if x["name"] == "ACN-Data Validation Workspace"), None) or checked(client.post("/api/enterprises", json={"name":"ACN-Data Validation Workspace","region":"US-CA","industry":"Public EV charging research validation","base_year":2018}))
        organization = next((x for x in checked(client.get("/api/organizations", params={"enterprise_id":enterprise["id"]})) if x.get("code") == "ACN-CALTECH"), None) or checked(client.post("/api/organizations", json={"enterprise_id":enterprise["id"],"name":"ACN Caltech Validation Site","level":"BUILDING_PARK","code":"ACN-CALTECH","metadata_json":{"data_class":"REAL_PUBLIC","dataset_id":"ACN_DATA_STATIC_CALTECH_2018_05"}}))
        site = next((x for x in checked(client.get("/api/sites", params={"enterprise_id":enterprise["id"]})) if x["code"] == "ACN-CALTECH"), None) or checked(client.post("/api/sites", json={"enterprise_id":enterprise["id"],"organization_node_id":organization["id"],"code":"ACN-CALTECH","name":"ACN Caltech EV Charging Validation Site","site_type":"CAMPUS","timezone":"America/Los_Angeles","metadata_json":{"data_class":"REAL_PUBLIC","dataset_id":"ACN_DATA_STATIC_CALTECH_2018_05","publisher":"Caltech / ACN-Data","source_url":"https://github.com/tongxin-li/ACN-Data-Static","access_method":"OFFICIAL_AUTHOR_STATIC_EXPORT","limitations":["not target-enterprise internal measurements","official REST API requires user token"]}}))
        system = next((x for x in checked(client.get("/api/energy-systems", params={"site_id":site["id"]})) if x["code"] == "ACN-EV-CHARGING"), None) or checked(client.post("/api/energy-systems", json={"site_id":site["id"],"code":"ACN-EV-CHARGING","name":"ACN California Garage 01 EV charging","system_type":"EV_CHARGING","metadata_json":{"data_class":"REAL_PUBLIC","dataset_id":"ACN_DATA_STATIC_CALTECH_2018_05"}}))
        path = NORMALIZED / "device_metrics.csv"
        source = next((x for x in checked(client.get("/api/data-sources", params={"enterprise_id":enterprise["id"]})) if x["name"] == "ACN-Data static session energy"), None) or checked(client.post("/api/data-sources", json={"enterprise_id":enterprise["id"],"name":"ACN-Data static session energy","source_type":"FILE","config_json":{"path":str(path.resolve()),"timezone":"UTC","field_mapping":{},"data_class":"REAL_PUBLIC","dataset_id":"ACN_DATA_STATIC_CALTECH_2018_05","source_url":"https://github.com/tongxin-li/ACN-Data-Static","transport":"FILE_OFFICIAL_AUTHOR_EXPORT","rest_validation_status":"BLOCKED_BY_ACCESS"}}))
        quality_before = checked(client.get(f"/api/data-sources/{source['id']}/data-quality"))
        sync = checked(client.post(f"/api/data-sources/{source['id']}/sync")) if quality_before["valid_records"] == 0 else {"extracted":quality_before["valid_records"],"inserted":quality_before["valid_records"],"quarantined":quality_before["quarantined_records"],"warnings":quality_before["warning_records"],"idempotent_resume":True}
        devices = checked(client.get("/api/devices", params={"enterprise_id":enterprise["id"],"data_source_id":source["id"]}))
        device_map = {x["external_id"]:x for x in devices}
        existing = {x["code"]:x for x in checked(client.get("/api/metering-points", params={"site_id":site["id"]}))}
        points=[]
        for station,device in device_map.items():
            code=f"MP-ACN-{station}"
            points.append(existing.get(code) or checked(client.post("/api/metering-points", json={"site_id":site["id"],"energy_system_id":system["id"],"device_id":device["id"],"data_source_id":source["id"],"code":code,"name":f"{station} session energy","metric_type":"energy_kwh","energy_type":"ELECTRICITY","unit":"kWh","metadata_json":{"data_class":"REAL_PUBLIC","dataset_id":"ACN_DATA_STATIC_CALTECH_2018_05","semantic_granularity":"SESSION_TOTAL_AT_DISCONNECT"}})))
        result={"access_status":"REST_BLOCKED_BY_ACCESS_TOKEN_REQUIRED","rest_scheduler_verified":False,"file_real_data_verified":True,"enterprise":enterprise,"site":site,"energy_system":system,"data_source":source,"sync":sync,"devices":devices,"metering_points":points,"quality":checked(client.get(f"/api/data-sources/{source['id']}/data-quality"))}
    (DATA / "manifests" / "acn_api_import_results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
