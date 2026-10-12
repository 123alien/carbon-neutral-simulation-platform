from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Building, CameraSpatialMapping, Site
from app.schemas.cross_camera import CrossCameraAdaptRequest


def _site(db: Session, site_id: int) -> Site:
    row = db.get(Site, site_id)
    if row is None:
        raise LookupError("园区不存在")
    return row


def _building_code(db: Session, building_id: int | None) -> str | None:
    if building_id is None:
        return None
    row = db.get(Building, building_id)
    return str((row.metadata_json or {}).get("building_id") or row.code) if row else None


def _mapping_response(db: Session, row: CameraSpatialMapping) -> dict:
    return {key: getattr(row, key) for key in ("id", "site_id", "building_id", "campus_id", "camera_id",
        "floor_id", "area_id", "longitude", "latitude", "anchor_source", "status", "metadata_json", "created_at", "updated_at")} | {
        "building_code": _building_code(db, row.building_id)}


def create_mapping(db: Session, data) -> dict:
    site = _site(db, data.site_id)
    expected_campus = str((site.metadata_json or {}).get("campus_id") or site.code)
    if data.campus_id != expected_campus:
        raise ValueError("摄像头 campus_id 与园区编码不一致")
    if data.building_id is not None:
        building = db.get(Building, data.building_id)
        if building is None or building.site_id != site.id:
            raise ValueError("摄像头建筑不属于当前园区")
    row = CameraSpatialMapping(**data.model_dump())
    db.add(row); db.commit(); db.refresh(row)
    return _mapping_response(db, row)


def update_mapping(db: Session, mapping_id: int, data) -> dict:
    row = db.get(CameraSpatialMapping, mapping_id)
    if row is None:
        raise LookupError("摄像头空间映射不存在")
    values = data.model_dump(exclude_unset=True)
    if "building_id" in values and values["building_id"] is not None:
        building = db.get(Building, values["building_id"])
        if building is None or building.site_id != row.site_id:
            raise ValueError("摄像头建筑不属于当前园区")
    for key, value in values.items():
        setattr(row, key, value)
    db.commit(); db.refresh(row)
    return _mapping_response(db, row)


def list_mappings(db: Session, campus_id: str, camera_id: str | None = None) -> list[dict]:
    stmt = select(CameraSpatialMapping).where(CameraSpatialMapping.campus_id == campus_id)
    if camera_id:
        stmt = stmt.where(CameraSpatialMapping.camera_id == camera_id)
    return [_mapping_response(db, row) for row in db.scalars(stmt.order_by(CameraSpatialMapping.camera_id)).all()]


def _passes_filters(filters, mapping: CameraSpatialMapping, building_code: str | None, start, end, score: float) -> bool:
    if score < filters.min_comprehensive_score:
        return False
    if filters.start_time and end < filters.start_time:
        return False
    if filters.end_time and start >= filters.end_time:
        return False
    if filters.camera_ids and mapping.camera_id not in filters.camera_ids:
        return False
    if filters.building_ids and building_code not in filters.building_ids:
        return False
    if filters.area_ids and mapping.area_id not in filters.area_ids:
        return False
    return True


def adapt(db: Session, data: CrossCameraAdaptRequest) -> dict:
    mappings = {row.camera_id: row for row in db.scalars(select(CameraSpatialMapping).where(
        CameraSpatialMapping.campus_id == data.campus_id, CameraSpatialMapping.status == "ACTIVE")).all()}
    all_nodes=[]; all_segments=[]; raw_tracks=[]; unmapped=set(); accepted_matches=0
    global_visits={}
    for match in data.matches:
        if match.comprehensive_score < data.filters.min_comprehensive_score:
            continue
        match_nodes=[]
        for track in sorted(match.tracks, key=lambda x: x.start_relative_time_s):
            raw_tracks.append({"global_id":match.global_id,"camera_id":track.camera_id,"local_id":track.local_id,
                "start_relative_time_s":track.start_relative_time_s,"end_relative_time_s":track.end_relative_time_s,
                "points":[point.model_dump() for point in track.points],"coordinate_system":"IMAGE_PIXEL",
                "gis_usage":"CAMERA_DETAIL_ONLY"})
            mapping=mappings.get(track.camera_id)
            start=track.start_time or data.video_start_time+timedelta(seconds=track.start_relative_time_s)
            end=track.end_time or data.video_start_time+timedelta(seconds=track.end_relative_time_s)
            if mapping is None:
                global_visits.setdefault(match.global_id,{})[(track.camera_id,track.local_id,start,end)]=(start,None)
                unmapped.add(track.camera_id);continue
            start=track.start_time or data.video_start_time+timedelta(seconds=track.start_relative_time_s)
            end=track.end_time or data.video_start_time+timedelta(seconds=track.end_relative_time_s)
            building_code=_building_code(db,mapping.building_id)
            if not _passes_filters(data.filters,mapping,building_code,start,end,match.comprehensive_score):
                global_visits.setdefault(match.global_id,{})[(track.camera_id,track.local_id,start,end)]=(start,None)
                continue
            match_nodes.append({"sequence":0,"global_id":match.global_id,"local_id":track.local_id,
                "campus_id":mapping.campus_id,"camera_id":mapping.camera_id,"building_id":building_code,
                "floor_id":mapping.floor_id,"area_id":mapping.area_id,"timestamp":start,"end_timestamp":end,
                "longitude":mapping.longitude,"latitude":mapping.latitude,"anchor_source":mapping.anchor_source,
                "match_similarity":match.match_similarity,"time_consistency":match.time_consistency,
                "comprehensive_score":match.comprehensive_score})
        match_nodes.sort(key=lambda x:x["timestamp"])
        for index,node in enumerate(match_nodes):node["sequence"]=index+1
        if match_nodes:accepted_matches+=1
        for node in match_nodes:
            key=(node['camera_id'],node['local_id'],node['timestamp'],node['end_timestamp'])
            visits=global_visits.setdefault(match.global_id,{})
            existing=visits.get(key)
            if existing is None or existing[1] is None or node['comprehensive_score']>existing[1]['comprehensive_score']:
                visits[key]=(node['timestamp'],node)
    for global_id,visits in global_visits.items():
        ordered=sorted(visits.values(),key=lambda x:x[0])
        sequence=0
        for _,node in ordered:
            if node is not None:
                sequence+=1;node['sequence']=sequence;all_nodes.append(node)
        for (_,left),(_,right) in zip(ordered,ordered[1:]):
            if left is None or right is None or left['camera_id']==right['camera_id']:
                continue
            all_segments.append({"global_id":global_id,"from_camera_id":left["camera_id"],"to_camera_id":right["camera_id"],
                "from_timestamp":left["end_timestamp"],"to_timestamp":right["timestamp"],
                "coordinates":[[left["longitude"],left["latitude"]],[right["longitude"],right["latitude"]]],
                "semantic":"CAMERA_REGION_TRANSITION",
                "disclaimer":"该线段表示相邻摄像头区域间的跨区域关联，不是人员真实连续步行GPS路径。"})
    return {"campus_id":data.campus_id,"video_start_time":data.video_start_time,"nodes":all_nodes,"segments":all_segments,
        "raw_pixel_tracks":raw_tracks,"raw_matches":[match.model_dump() for match in data.matches],"unmapped_camera_ids":sorted(unmapped),"filtered_match_count":accepted_matches,
        "source_match_count":len(data.matches),"coordinate_semantics":"CAMERA_OR_AREA_ANCHOR",
        "disclaimer":"GIS轨迹是摄像头区域节点间的关联结果，像素轨迹仅用于摄像头内详情。"}
