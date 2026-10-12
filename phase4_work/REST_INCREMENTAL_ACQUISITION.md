# REST 增量采集与分页

版本基线：Backend V1.0.0-alpha.11、Frontend V1.0.0-beta.15、Alembic `017_p3_5_2_1`。

## 模式与配置

- `incremental_mode`: `NONE`（兼容原单次拉取）或 `TIME_WINDOW`。`CURSOR` 仅保留设计方向，本版本未实现、未标记 VERIFIED。
- `TIME_WINDOW`: 必须配置 `start_param`、`end_param` 和首次运行的 `initial_start`。内部 watermark 统一为 UTC；`api_timezone`（IANA）与 `time_format` 仅控制发给第三方接口的序列化。
- `overlap_minutes`: 默认 10 分钟，可配置 0–60 分钟。下一轮起点为 `last_success_watermark - overlap`。
- `pagination_mode`: `NONE` 或 `LINK_NEXT`。Next 路径默认 `_links.next.href`，支持相对或绝对 URL。
- `max_pages`: 默认 100；`max_records_per_run` 可选。重复请求 URL抛出 `PAGINATION_LOOP`；超过限制会失败，且 watermark 不推进。
- `source_record_id_path`: 支持 `id`、`sessionID`、`external.id` 等点路径，不绑定具体供应商。

## 成功边界、幂等与恢复

`last_success_at` 是任务完成时间；`last_success_watermark` 是成功覆盖的业务数据时间边界。只有请求、全部分页、字段映射、L1/L2/L3 与持久化全部完成后，watermark 才推进到窗口终点。任一页失败时保留原 watermark，下一周期重拉同一窗口。

幂等优先级为 `(data_source_id, source_record_id, metric_name)`（存于 `external_record_dedup`），无外部 ID 时回退到既有 `(device_id, timestamp, metric_name)`。`DeviceMetric` 未增加强制字段或新约束。

## 验证结论

隔离 HTTP 服务验证：首次 `00:00 → 01:00` 完成多页处理后 watermark 为 `01:00`；第二次从 `00:50 → 02:00` 拉取，重复跳过、新记录入库，watermark 为 `02:00`。还覆盖单页、Next 缺失、五页分页、Next 循环、最大页数、第二页失败不推进、调度第二轮窗口及服务重建后从数据库恢复 watermark。

ACN fixture 仅用于验证 `where`、`sort` 与 `_links.next.href` 协议形态。当前无合法 `ACN_API_TOKEN`，ACN 官方公网 REST 自动采集继续为 `BLOCKED_BY_ACCESS`。未来仅在显式设置 `RUN_REAL_PUBLIC_ACN=1` 与合法 Token 时执行公网验证。
