# 跨镜轨迹 GIS 适配层

## 边界

本适配层不连接当前局域网服务，不生成模拟轨迹，不推断学生、教师或访客类别。它只完成：

1. 摄像头与校园空间锚点的管理。
2. 将相对视频秒数转换为带时区的 ISO 8601 绝对时间。
3. 保留像素轨迹，但不将像素坐标投影到 GIS。
4. 用同一 Global ID 的摄像头序列生成跨区域 GIS 节点和关联线段。

同一 Global ID 的多条匹配按时间合并；相同摄像头、Local ID 和起止时间的节点去重。筛选或未映射的中间节点不会被跳过后强行连接两端。`raw_matches` 完整保留输入匹配信息，包含两个摄像头的 Local ID、评分及 `upstream_raw`。

## API

- `POST /api/cross-camera-adapter/camera-mappings`：新增摄像头空间锚点。
- `PUT /api/cross-camera-adapter/camera-mappings/{mapping_id}`：更新锚点。
- `GET /api/cross-camera-adapter/camera-mappings?campus_id=HBUE`：查询映射。
- `POST /api/cross-camera-adapter/adapt`：对已获取的上游匹配和轨迹数据做纯适配，不主动访问上游。

## 坐标语义

- `raw_pixel_tracks.points`：`IMAGE_PIXEL`，仅摄像头内详情使用。
- `nodes.longitude/latitude`：摄像头实际位置或经核对的区域锚点。
- `segments`：相邻摄像头区域之间的关联线，不是人员真实连续步行 GPS 路径。

## 筛选能力

当前适配支持：

- 最低综合匹配分数
- 绝对时间范围
- 摄像头
- 建筑
- 区域

不包含人员类别筛选。

## 待联调项

正式联调时只需增加“徐旺旺局域网 API 响应 → `CrossCameraAdaptRequest`”的字段转换，GIS 节点、线段、筛选和摄像头映射逻辑无需重写。
