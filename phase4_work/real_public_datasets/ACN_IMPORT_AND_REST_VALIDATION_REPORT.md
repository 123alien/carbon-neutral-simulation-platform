# P3-5.2 ACN-Data 导入与 REST 验证报告

## 官方访问审计

- 官方入口：`https://ev.caltech.edu/api/v1/sessions/{site}`；带时序端点为 `/ts`。
- Authentication：必须注册，Token 作为 HTTP Basic 用户名使用；本机 `ACN_API_TOKEN`、`ACN_DATA_TOKEN`、`ACNDATA_TOKEN` 均未配置。
- 无凭证真实请求结果：HTTP 401。
- 查询：`where` 支持时间条件；`sort` 支持排序；普通 Session 每页 25 条，时序每页 1 条；分页由 `_links.next` 和 `_meta` 描述。
- 访问状态：`MANUAL_ACCESS_REQUIRED / BLOCKED_BY_ACCESS`。
- REST Scheduler：未启动、未伪造成功、实际认证后 API 请求次数为 0。

## 合法静态数据替代验证

- 数据源：ACN-Data 论文作者维护的 `tongxin-li/ACN-Data-Static`。
- Site：Caltech / California_Garage_01，与 BDG2 Site 完全隔离。
- Station：3；Session：122；原始采样点：359,029。
- 时间：2018-05-01 至 2018-05-14 的连接会话，实际最后采样到 2018-05-15 00:15:40 UTC。
- 输出：`cleaned/acn_data/.../sessions.csv`、`normalized/acn_data/.../devices.csv`、`metering_points.csv`、`device_metrics.csv`。
- 哈希：122 个原始 `.csv.gz` 及全部输出的 SHA-256 均保存在 `manifests/acn_caltech_2018_05_manifest.json`。

## 字段映射与粒度

| ACN 静态字段 | 平台字段 | 说明 |
|---|---|---|
| filename station prefix | Device.external_id | 稳定 EVSE ID |
| filename | source_session_id | 原始会话唯一标识，保留在 raw_json |
| first timestamp | connection_time | UTC |
| last timestamp | DeviceMetric.timestamp | 会话最后真实采样时刻 |
| last non-zero current timestamp | done_charging_time | 无非零电流则缺失 |
| max cumulative Energy Delivered | energy_kwh | 会话总电量，不是小时电量 |
| America/Los_Angeles | Site.timezone | API 聚合已验证返回 `-07:00` |

当前 Field Mapping 不支持通用 nested dot path；本轮静态 CSV 不需要该能力。Session 的连接/断开一致性不属于现有 DeviceMetric L2 规则，已在预处理质量报告独立校验。L3 duplicate/future timestamp 对落库事实适用；temporal gap 对不规则 Session 事件为 `NOT_APPLICABLE`。

## API 导入结果

- Site：1 个独立 ACN Validation Site。
- EnergySystem：1 个 `EV_CHARGING`。
- Device：3 个 `EV_CHARGER`。
- MeteringPoint：3 个，单位 kWh，语义 `SESSION_TOTAL_AT_DISCONNECT`。
- FILE Adapter：received 116、persisted 116、rejected 0、warnings 0。
- 总交付电量：812.5449808333221 kWh。
- Device 页面 API：设备类型、Station ID、最新会话时间、质量状态可读取。
- 日聚合：基于真实会话结束日求和；没有推导 charging power curve。

数据库导入前后：Site 1→2，EnergySystem 1→2，Device 5→8，MeteringPoint 5→8，DeviceMetric 43,910→44,026，DataSource 1→2，RuntimeState 0→0。Alembic 保持 `016_p3_4`。

## REST 增量审计

现有 RestApiAdapter 只支持固定 URL、单次 JSON list 和 `data_path`，没有 `_links.next` 分页、watermark 或窗口参数注入。ACN 官方接口明确需要 `where` 时间窗口与分页，所以重复定时拉取会重复读取第一页或固定结果；依赖 Device+timestamp+metric 的 L3 只能拒绝重复，不能降低远端流量。

推荐后续最小能力：`TIME_WINDOW`（start/end 参数模板、last-success watermark、5–15 分钟 overlap）加 HATEOAS `next` 分页，并为 Session 事实评估 `source_record_id`。由于当前没有合法 Token，尚不能做真实集成验证，本轮没有把未验证设计写入生产 Adapter。

## 仿真、推荐与报告

- Simulation：`INPUT_GRANULARITY_NOT_SUPPORTED`。真实输入是 Session 事件总量，不强制转换为小时 EV profile。
- Recommendation：未运行；没有匹配的真实电价，不能声称经济收益。
- Report：没有有效 SimulationTask，现有 ReportEngine 强制绑定任务，因此未创建假任务或零值报告；`FUNCTION_GAP`。
- Report provenance 代码能力已在 P3-5 第一轮验证，但 ACN 专属正式报告需在获得真实时序/合法小时聚合口径后执行。

## 结论

- EV 公开真实数据、EV_CHARGER、Device、MeteringPoint、DeviceMetric、FILE、字段标准化和 L1/L2/L3：`VERIFIED`。
- 官方 ACN REST 自动采集、Scheduler Runtime、分页/增量：`BLOCKED_BY_ACCESS / NOT_VERIFIED`。
- 没有使用本地 mock 作为真实性证据，没有保存或输出 Token，没有把 Caltech 数据称为企业内部数据。

## 回归验证

- Backend：47 passed，2 skipped；新增官方 ACN 公网测试默认跳过，只有 `RUN_REAL_PUBLIC_ACN=1` 时运行。
- Playwright：13 passed；ACN 专项确认独立 Site、3 个 EV_CHARGER、真实日聚合、`America/Los_Angeles` 的 `-07:00` 时区和无 NaN。
- `vue-tsc -b` 与 `vite build`：通过；仅保留既有大 chunk 警告。
- Token 安全：开发 DataSource `has_credentials=false`；配置、manifest 和报告均无 Token 或 Authorization 值。
