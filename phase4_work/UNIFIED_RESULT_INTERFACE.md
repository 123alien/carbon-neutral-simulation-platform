# 统一展示层结果接口

本接口是碳中和仿真平台向未来统一展示层提供的只读结果契约，不读取、不写入、不模拟跨镜追踪数据。

## 接口

- `GET /api/result-interface/campuses/{site_id}/overview`：校园总览结果。
- `GET /api/result-interface/campuses/{site_id}/buildings`：建筑级能耗与碳排结果。
- `GET /api/result-interface/campuses/{site_id}/simulation`：多场景与长期路径仿真结果。
- `GET /api/result-interface/campuses/{site_id}/carbon-market?region=...`：碳市场指标与碳成本结果。

## 空间关联契约

建筑级每条结果固定返回：

```json
{
  "campus_id": "HBUE",
  "building_id": "HBUE-B001",
  "floor_id": null,
  "area_id": null,
  "timestamp": "2024-01-07T15:00:00"
}
```

`floor_id` 和 `area_id` 为 `null` 表示当前结果是楼栋级聚合，不会为了对接而伪造楼层或区域粒度。时间戳优先使用该建筑最新业务数据时间，无数据时使用本次查询时间。

## 边界

- 所有接口仅做现有业务数据的聚合查询。
- 空数据返回 `null` 或空列表，不伪造结果。
- 示范校园数据继续显式标识为“示范仿真数据”。
- 跨镜系统未列入依赖，本次不新增人员、车辆或事件字段。
