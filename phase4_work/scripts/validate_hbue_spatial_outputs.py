"""Validate generated HBUE polygons and remove bbox neighbours crossing the campus boundary."""
from __future__ import annotations
import csv,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUTS=[ROOT/"spatial_data"/"hbue",ROOT/"frontend"/"public"/"data"/"hbue"]
def inside(point,ring):
    x,y=point;ok=False;j=len(ring)-1
    for i,(xi,yi) in enumerate(ring):
        xj,yj=ring[j]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/((yj-yi) or 1e-15)+xi:ok=not ok
        j=i
    return ok
def run(output:Path):
    boundary=json.loads((output/"hbue_campus_boundary.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"]["coordinates"][0]
    collection=json.loads((output/"hbue_buildings.geojson").read_text(encoding="utf-8"));kept=[];removed=[]
    for feature in collection["features"]:
        ring=feature["geometry"]["coordinates"][0]
        (kept if all(inside(p,boundary) or p in boundary for p in ring[:-1]) else removed).append(feature)
    collection["features"]=kept;(output/"hbue_buildings.geojson").write_text(json.dumps(collection,ensure_ascii=False,indent=2),encoding="utf-8")
    ids={x["properties"]["building_id"] for x in kept}
    with (output/"hbue_building_centroids.csv").open(encoding="utf-8-sig") as file:centroids=[r for r in csv.DictReader(file) if r["building_id"] in ids]
    with (output/"hbue_building_centroids.csv").open("w",newline="",encoding="utf-8-sig") as file:w=csv.DictWriter(file,fieldnames=centroids[0].keys());w.writeheader();w.writerows(centroids)
    with (output/"hbue_building_mapping.csv").open(encoding="utf-8-sig") as file:mapping=list(csv.DictReader(file))
    for row in mapping:
        triples=list(zip(row["matched_building_ids"].split(";"),row["matched_osm_names"].split(";"),row["osm_ids"].split(";"))) if row["matched_building_ids"] else []
        triples=[x for x in triples if x[0] in ids]
        row["matched_building_ids"]=";".join(x[0] for x in triples);row["matched_osm_names"]=";".join(x[1] for x in triples);row["osm_ids"]=";".join(x[2] for x in triples)
        if not triples:row.update(status="pending_confirmation",name_source="",verification_note="未找到完全位于校园边界内的可靠具名建筑面，未强行匹配")
    with (output/"hbue_building_mapping.csv").open("w",newline="",encoding="utf-8-sig") as file:w=csv.DictWriter(file,fieldnames=mapping[0].keys());w.writeheader();w.writerows(mapping)
    summary=json.loads((output/"summary.json").read_text(encoding="utf-8"));summary.update(building_count=len(kept),confirmed_named_count=sum(bool(x["properties"]["verified"]) for x in kept),unknown_count=sum(not x["properties"]["verified"] for x in kept),requested_confirmed_count=sum(x["status"]=="confirmed" for x in mapping),requested_pending_count=sum(x["status"]!="confirmed" for x in mapping),boundary_validation="all building vertices inside campus boundary",excluded_cross_boundary=[x["properties"]["osm_id"] for x in removed]);(output/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary
if __name__=="__main__":print(json.dumps(run(OUTPUTS[0]),ensure_ascii=False,indent=2));run(OUTPUTS[1])
