"""Import CBECS annual activities through the public application API (never SQL)."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "cbecs2018"
API = "http://127.0.0.1:8000"
RUN_NAME = "EIA CBECS 2018 official multi-energy Scope 1/2 validation"
REGION = "US-CBECS-NATIONAL"


def checked(response: httpx.Response):
    if not response.is_success:
        raise RuntimeError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text[:1200]}")
    return response.json()


def main() -> None:
    buildings = pd.read_csv(DATA / "normalized" / "buildings.csv").to_dict("records")
    activities = pd.read_csv(DATA / "normalized" / "accounting_activities.csv").to_dict("records")
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    with httpx.Client(base_url=API, timeout=180, trust_env=False) as client:
        checked(client.get("/health"))
        enterprise = next((x for x in checked(client.get("/api/enterprises")) if x["name"] == "EIA CBECS 2018 Scope 1 Validation"), None) or checked(client.post("/api/enterprises", json={"name":"EIA CBECS 2018 Scope 1 Validation","region":REGION,"industry":"Official US commercial-building survey validation","base_year":2018}))
        orgs = checked(client.get("/api/organizations", params={"enterprise_id": enterprise["id"]}))
        root = next((x for x in orgs if x.get("code") == "CBECS-SCOPE1"), None) or checked(client.post("/api/organizations", json={"enterprise_id":enterprise["id"],"name":"CBECS Scope 1 Validation Organization","level":"ENTERPRISE","code":"CBECS-SCOPE1","metadata_json":{"data_class":"REAL_PUBLIC_OFFICIAL","dataset":"EIA CBECS 2018"}}))
        site = next((x for x in checked(client.get("/api/sites", params={"enterprise_id":enterprise["id"]})) if x["code"] == "CBECS-SCOPE1"), None) or checked(client.post("/api/sites", json={"enterprise_id":enterprise["id"],"organization_node_id":root["id"],"code":"CBECS-SCOPE1","name":"Scope1 Validation Site · EIA CBECS 2018","site_type":"OTHER","timezone":"UTC","metadata_json":{"data_class":"REAL_PUBLIC_OFFICIAL","dataset":"EIA CBECS 2018 Final Public Use Microdata","survey_granularity":"ANNUAL","country":"United States","not_target_china_site":True,"public_microdata_is_masked":True}}))

        orgs = checked(client.get("/api/organizations", params={"enterprise_id":enterprise["id"]}))
        existing_buildings = {x["code"]: x for x in checked(client.get(f"/api/sites/{site['id']}/buildings"))}
        org_map, building_map = {}, {}
        for row in buildings:
            code = row["building_code"]
            org = next((x for x in orgs if x.get("code") == code), None) or checked(client.post("/api/organizations", json={"enterprise_id":enterprise["id"],"parent_id":root["id"],"name":row["name"],"level":"BUILDING_PARK","code":code,"metadata_json":{"data_class":"REAL_PUBLIC_OFFICIAL","survey_year":2018}}))
            org_map[code] = org
            building_map[code] = existing_buildings.get(code) or checked(client.post(f"/api/sites/{site['id']}/buildings", json={"organization_node_id":org["id"],"code":code,"name":row["name"],"building_type":row["building_type"],"area_m2":row["floor_area_m2"],"metadata_json":{"data_class":"REAL_PUBLIC_OFFICIAL","original_floor_area_sqft":row["floor_area_sqft"],"survey_year":2018,"identity":"masked CBECS public-use building"}}))

        existing_run = next((x for x in checked(client.get("/api/carbon-accounting/runs", params={"enterprise_id":enterprise["id"]})) if x["name"] == RUN_NAME), None)
        factor_sources = {
            "electricity":"US EPA 2020 GHG Emission Factors Hub, eGRID2018 U.S. average output rates; AR4 GWP",
            "natural_gas":"US EPA 2020 GHG Emission Factors Hub, Table 1 stationary combustion; AR4 GWP",
            "oil":"US EPA 2020 GHG Emission Factors Hub, Distillate Fuel Oil No. 2; AR4 GWP",
            "heat":"US EPA 2020 GHG Emission Factors Hub, Table 7 purchased steam/heat; AR4 GWP",
        }
        if not existing_run:
            for energy_type, factor in manifest["factors"].items():
                checked(client.post("/api/emission-factors", json={"region":REGION,"year":2018,"energy_type":energy_type,"factor":factor["value"],"unit":factor["unit"],"source":factor_sources[energy_type],"version":"EPA-HUB-2020-eGRID2018-AR4"}))
            activity_payload = []
            for row in activities:
                activity_payload.append({"timestamp":row["timestamp"],"energy_type":row["energy_type"],"value":row["value"],"unit":row["unit"],"organization_node_id":org_map[row["building_code"]]["id"],"scope":row["scope"],"source":f"REAL_PUBLIC_OFFICIAL | EIA CBECS 2018 PUBID {row['building_code'].removeprefix('CBECS-')} | field {row['source_field']} | annual 2018"})
            run = checked(client.post("/api/carbon-accounting/runs", json={"enterprise_id":enterprise["id"],"name":RUN_NAME,"period_start":"2018-01-01T00:00:00Z","period_end":"2019-01-01T00:00:00Z","scopes":["SCOPE_1","SCOPE_2"],"standard_basis":"GHG Protocol Corporate Standard; EIA CBECS 2018; US EPA GHG Emission Factors Hub 2020; eGRID2018; IPCC AR4 GWP","activities":activity_payload,"include_device_metrics":False}))
        else:
            run = existing_run

        results = checked(client.get(f"/api/carbon-accounting/runs/{run['id']}/results"))
        stats_scope = checked(client.get(f"/api/carbon-accounting/runs/{run['id']}/statistics", params={"granularity":"year","dimension":"scope","timezone":"UTC"}))
        site_carbon = checked(client.get(f"/api/sites/{site['id']}/carbon", params={"start_time":"2018-01-01T00:00:00Z","end_time":"2019-01-01T00:00:00Z","granularity":"year"}))
        building_carbon = {code: checked(client.get(f"/api/buildings/{building['id']}/carbon", params={"start_time":"2018-01-01T00:00:00Z","end_time":"2019-01-01T00:00:00Z","granularity":"year"})) for code, building in building_map.items()}
        actual = {energy: sum(x["emission_t"] for x in results if x["energy_type"] == energy) for energy in manifest["factors"]}
        for energy, expected in manifest["expected_emissions_tco2e"].items():
            if abs(actual[energy] - expected) > 1e-6:
                raise RuntimeError(f"{energy} expected {expected}, received {actual[energy]}")
        report = {"enterprise":enterprise,"site":site,"buildings":building_map,"run":run,"result_count":len(results),"emissions_tco2e":actual,"total_tco2e":sum(actual.values()),"scope_statistics":stats_scope,"site_carbon":site_carbon,"building_carbon":building_carbon,"factor_sources":factor_sources,"api_only":True}
        (DATA / "import_result.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"site_id":site["id"],"run_id":run["id"],"result_count":len(results),"emissions_tco2e":actual,"total_tco2e":sum(actual.values())}, indent=2))


if __name__ == "__main__":
    main()
