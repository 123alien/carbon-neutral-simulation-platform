"""Build the HBUE WGS84 spatial baseline from OpenStreetMap.

Sources are downloaded at execution time. No coordinate or footprint is invented.
Unlabelled OSM footprints remain unknown_building_<osm_id> and unverified.
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CAMPUS_ID = "HBUE"
CAMPUS_OSM_ID = 908384239
CENTER = (30.42023, 114.42966)
ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = [ROOT / "spatial_data" / "hbue", ROOT / "frontend" / "public" / "data" / "hbue"]
OVERPASS_ENDPOINTS = ["https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter", "https://overpass-api.de/api/interpreter"]
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "HBUE-Spatial-Baseline/1.0 (carbon-neutrality-platform)"

EXTRA_NAMED_OUTLINES = {101939167, 101939159, 101792298}  # 实验楼二、实验楼一、室内体育馆
REQUESTED = [
    "行政楼", "群贤楼", "知行楼", "教学楼1", "教学楼2", "教学楼3", "教学楼4", "实验楼",
    "图书馆", "体育馆", "大学生活动中心", "学生事务中心", "人文艺术楼", "法商大楼", "学生公寓",
    "校医院", "食堂/商业服务建筑", "创意产业教研与实训大楼（香帅楼）",
]
ALIASES = {
    "行政楼": ["湖北经济学院行政楼"], "群贤楼": ["群贤楼"], "知行楼": ["知行楼"],
    "教学楼1": ["教学楼一"], "教学楼2": ["教学楼二"], "教学楼3": ["教学楼三"],
    "教学楼4": [], "实验楼": ["实验楼一", "实验楼二"], "图书馆": [], "体育馆": ["室内体育馆"],
    "大学生活动中心": ["大学生活动中心"], "学生事务中心": [], "人文艺术楼": ["人文艺术楼"],
    "法商大楼": ["法商学院综合楼"], "学生公寓": ["宿舍楼", "湖北经济学院枫苑宿舍", "桂苑1栋"],
    "校医院": ["校医院"], "食堂/商业服务建筑": ["一粟堂", "三清园", "七品居", "九华厅", "藏龙美食城", "商业街", "商业建筑群"],
    "创意产业教研与实训大楼（香帅楼）": ["香帅楼"],
}


def get_json(url: str, data: bytes | None = None) -> dict | list:
    request = Request(url, data=data, headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"})
    with urlopen(request, timeout=240) as response:
        return json.load(response)


def polygon_ring(geometry: dict) -> list[list[float]]:
    if geometry["type"] == "Polygon":
        return geometry["coordinates"][0]
    raise ValueError(f"Unsupported campus geometry: {geometry['type']}")


def centroid(ring: list[list[float]]) -> tuple[float, float]:
    points = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def inside(point: tuple[float, float], ring: list[list[float]]) -> bool:
    x, y = point
    result = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-15) + xi:
            result = not result
        j = i
    return result


def classify(name: str, osm_building: str) -> str:
    if any(x in name for x in ("教学", "知行", "群贤", "实验")): return "teaching"
    if "图书" in name: return "library"
    if any(x in name for x in ("体育", "活动中心")): return "public_activity"
    if any(x in name for x in ("行政", "学术交流", "人文艺术", "法商", "香帅", "笃行")): return "office"
    if any(x in name for x in ("宿舍", "桂苑", "竹", "桔", "梅", "栎")) or osm_building in {"apartments", "dormitory"}: return "dormitory"
    if any(x in name for x in ("食堂", "一粟堂", "三清园", "七品居", "九华厅", "美食", "商业")): return "commercial_service"
    if "医院" in name or osm_building == "hospital": return "healthcare"
    return "other"


def download() -> tuple[dict, list[dict]]:
    print("正在读取校园边界…", flush=True)
    search = get_json(NOMINATIM + "?" + urlencode({"format":"jsonv2", "polygon_geojson":1, "limit":5, "q":"湖北经济学院 武汉"}))
    campus = next(item for item in search if item.get("osm_type") == "way" and int(item.get("osm_id", 0)) == CAMPUS_OSM_ID)
    south, north, west, east = map(float, campus["boundingbox"])
    query = f'''[out:json][timeout:180];way[building]({south},{west},{north},{east});out tags center geom;'''
    payload = urlencode({"data": query}).encode()
    print("正在读取校园建筑轮廓…", flush=True)
    last_error=None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            result = get_json(endpoint, payload)
            break
        except Exception as error:
            last_error=error
            print(f"建筑服务暂不可用，切换备用节点：{endpoint}", flush=True)
    else:
        raise RuntimeError("全部 Overpass 节点均不可用") from last_error
    extras=[]
    for osm_id in sorted(EXTRA_NAMED_OUTLINES):
        full=get_json(f"https://api.openstreetmap.org/api/0.6/way/{osm_id}/full.json")
        nodes={node["id"]:node for node in full["elements"] if node["type"]=="node"}
        way=next(item for item in full["elements"] if item["type"]=="way" and item["id"]==osm_id)
        way["geometry"]=[{"lat":nodes[node_id]["lat"],"lon":nodes[node_id]["lon"]} for node_id in way["nodes"]]
        extras.append(way)
    result["elements"].extend(extras)
    print(f"已读取 {len(result['elements'])} 个候选轮廓", flush=True)
    return campus, result["elements"]


def build() -> dict:
    campus, elements = download()
    boundary_ring = polygon_ring(campus["geojson"])
    raw = []
    for element in elements:
        geometry = element.get("geometry") or []
        if len(geometry) < 3:
            continue
        ring = [[float(node["lon"]), float(node["lat"])] for node in geometry]
        if ring[0] != ring[-1]: ring.append(ring[0])
        center = centroid(ring)
        # A footprint is accepted only when every vertex lies inside the mapped
        # campus boundary; bbox neighbours and boundary-crossing objects are excluded.
        if all(inside(tuple(point), boundary_ring) or point in boundary_ring for point in ring[:-1]):
            raw.append((int(element["id"]), element.get("tags") or {}, ring, center))
    raw.sort(key=lambda row: row[0])
    features, centroid_rows = [], []
    for index, (osm_id, tags, ring, center) in enumerate(raw, 1):
        osm_name = str(tags.get("name") or "").strip()
        name = osm_name or f"unknown_building_{osm_id}"
        building_id = f"HBUE-B{index:03d}"
        verified = bool(osm_name)
        building_type = classify(name, str(tags.get("building") or ""))
        properties = {
            "campus_id": CAMPUS_ID, "building_id": building_id, "name": name,
            "name_source": "osm" if osm_name else "osm_unlabelled", "osm_id": f"way/{osm_id}",
            "building_type": building_type, "verified": verified,
            "source": "OpenStreetMap contributors (ODbL)", "source_url": f"https://www.openstreetmap.org/way/{osm_id}",
        }
        features.append({"type":"Feature", "properties":properties, "geometry":{"type":"Polygon", "coordinates":[ring]}})
        centroid_rows.append({"building_id":building_id, "building_name":name, "longitude":f"{center[0]:.7f}", "latitude":f"{center[1]:.7f}", "building_type":building_type, "source":"OpenStreetMap", "verified":str(verified).lower()})
    by_name: dict[str, list[dict]] = {}
    for feature in features: by_name.setdefault(feature["properties"]["name"], []).append(feature)
    mapping_rows=[]
    for requested in REQUESTED:
        matched=[feature for alias in ALIASES[requested] for feature in by_name.get(alias, [])]
        mapping_rows.append({
            "requested_name":requested,
            "status":"confirmed" if matched else "pending_confirmation",
            "matched_building_ids":";".join(x["properties"]["building_id"] for x in matched),
            "matched_osm_names":";".join(x["properties"]["name"] for x in matched),
            "osm_ids":";".join(x["properties"]["osm_id"] for x in matched),
            "name_source":"osm" if matched else "",
            "verification_note":"OSM建筑面名称与公开名称一致" if matched else "未找到可可靠对应的具名建筑面，未强行匹配",
        })
    boundary = {"type":"FeatureCollection", "name":"湖北经济学院校园边界", "crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:OGC:1.3:CRS84"}}, "features":[{"type":"Feature","properties":{"campus_id":CAMPUS_ID,"name":"湖北经济学院","osm_id":f"way/{CAMPUS_OSM_ID}","source":"OpenStreetMap Nominatim / ODbL","verified":True},"geometry":campus["geojson"]}]}
    buildings = {"type":"FeatureCollection", "name":"湖北经济学院建筑轮廓", "crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:OGC:1.3:CRS84"}}, "features":features}
    for output in OUTPUTS:
        output.mkdir(parents=True, exist_ok=True)
        (output/"hbue_campus_boundary.geojson").write_text(json.dumps(boundary,ensure_ascii=False,indent=2),encoding="utf-8")
        (output/"hbue_buildings.geojson").write_text(json.dumps(buildings,ensure_ascii=False,indent=2),encoding="utf-8")
        with (output/"hbue_building_centroids.csv").open("w",newline="",encoding="utf-8-sig") as file:
            writer=csv.DictWriter(file,fieldnames=centroid_rows[0].keys());writer.writeheader();writer.writerows(centroid_rows)
        with (output/"hbue_building_mapping.csv").open("w",newline="",encoding="utf-8-sig") as file:
            writer=csv.DictWriter(file,fieldnames=mapping_rows[0].keys());writer.writeheader();writer.writerows(mapping_rows)
    summary={"campus_osm_id":CAMPUS_OSM_ID,"building_count":len(features),"confirmed_named_count":sum(x["properties"]["verified"] for x in features),"unknown_count":sum(not x["properties"]["verified"] for x in features),"requested_confirmed_count":sum(x["status"]=="confirmed" for x in mapping_rows),"requested_pending_count":sum(x["status"]!="confirmed" for x in mapping_rows),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
    for output in OUTPUTS:(output/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
