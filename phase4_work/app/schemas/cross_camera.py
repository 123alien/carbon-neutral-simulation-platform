from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from .common import ORMModel


class CameraSpatialMappingCreate(ORMModel):
    site_id: int
    building_id: int | None = None
    campus_id: str
    camera_id: str
    floor_id: str | None = None
    area_id: str | None = None
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    anchor_source: str = "CAMERA_LOCATION"
    status: str = "ACTIVE"
    metadata_json: dict = Field(default_factory=dict)


class CameraSpatialMappingUpdate(ORMModel):
    building_id: int | None = None
    floor_id: str | None = None
    area_id: str | None = None
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    anchor_source: str | None = None
    status: str | None = None
    metadata_json: dict | None = None


class CameraSpatialMappingRead(CameraSpatialMappingCreate):
    id: int
    building_code: str | None = None
    created_at: datetime
    updated_at: datetime


class PixelCenter(ORMModel):
    x: float
    y: float


class PixelTrajectoryPoint(ORMModel):
    relative_time_s: float = Field(ge=0)
    x: float
    y: float
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)
    center: PixelCenter | None = None
    direction: str | float | dict[str, float] | None = None
    speed: float | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)


class CameraPixelTrack(ORMModel):
    camera_id: str
    local_id: str
    start_relative_time_s: float = Field(default=0,ge=0)
    end_relative_time_s: float = Field(default=0,ge=0)
    points: list[PixelTrajectoryPoint] = Field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None

    @model_validator(mode="after")
    def validate_times(self):
        if self.end_relative_time_s < self.start_relative_time_s:
            raise ValueError("end_relative_time_s cannot be before start_relative_time_s")
        for value in (self.start_time,self.end_time):
            if value is not None and value.tzinfo is None:
                raise ValueError('upstream absolute time must include timezone')
        return self


class CrossCameraMatch(ORMModel):
    global_id: str
    camera_a_id: str
    local_id_a: str
    camera_b_id: str
    local_id_b: str
    match_similarity: float = Field(ge=0, le=1)
    time_consistency: float = Field(ge=0, le=1)
    comprehensive_score: float = Field(ge=0, le=1)
    tracks: list[CameraPixelTrack]
    upstream_raw: dict[str, Any] | None = None


class CrossCameraFilter(ORMModel):
    min_comprehensive_score: float = Field(default=0, ge=0, le=1)
    start_time: datetime | None = None
    end_time: datetime | None = None
    camera_ids: list[str] = Field(default_factory=list)
    building_ids: list[str] = Field(default_factory=list)
    area_ids: list[str] = Field(default_factory=list)


class CrossCameraAdaptRequest(ORMModel):
    campus_id: str
    video_start_time: datetime
    matches: list[CrossCameraMatch]
    filters: CrossCameraFilter = Field(default_factory=CrossCameraFilter)

    @model_validator(mode="after")
    def validate_absolute_time_origin(self):
        if self.video_start_time.tzinfo is None:
            raise ValueError("video_start_time must include a timezone offset")
        if self.filters.start_time and self.filters.start_time.tzinfo is None:
            raise ValueError("filter start_time must include a timezone offset")
        if self.filters.end_time and self.filters.end_time.tzinfo is None:
            raise ValueError("filter end_time must include a timezone offset")
        if self.filters.start_time and self.filters.end_time and self.filters.start_time >= self.filters.end_time:
            raise ValueError("filter start_time must be before end_time")
        return self


class GisTrajectoryNode(ORMModel):
    sequence: int
    global_id: str
    local_id: str
    campus_id: str
    camera_id: str
    building_id: str | None
    floor_id: str | None
    area_id: str | None
    timestamp: datetime
    end_timestamp: datetime
    longitude: float
    latitude: float
    anchor_source: str
    match_similarity: float
    time_consistency: float
    comprehensive_score: float


class GisTrajectorySegment(ORMModel):
    global_id: str
    from_camera_id: str
    to_camera_id: str
    from_timestamp: datetime
    to_timestamp: datetime
    coordinates: list[list[float]]
    semantic: str = "CAMERA_REGION_TRANSITION"
    disclaimer: str = "该线段表示相邻摄像头区域间的跨区域关联，不是人员真实连续步行GPS路径。"


class CrossCameraAdaptResponse(ORMModel):
    campus_id: str
    video_start_time: datetime
    nodes: list[GisTrajectoryNode]
    segments: list[GisTrajectorySegment]
    raw_pixel_tracks: list[dict]
    raw_matches: list[CrossCameraMatch]
    unmapped_camera_ids: list[str]
    filtered_match_count: int
    source_match_count: int
    coordinate_semantics: str = "CAMERA_OR_AREA_ANCHOR"
    disclaimer: str = "GIS轨迹是摄像头区域节点间的关联结果，像素轨迹仅用于摄像头内详情。"
