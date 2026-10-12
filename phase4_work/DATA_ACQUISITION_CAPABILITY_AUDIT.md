# 多源数据采集能力审计（P3-3）

审计基线：Frontend V1.0.0-beta.15、Backend V1.0.0-alpha.11、Alembic `017_p3_5_2_1`。

P3-5.2.1 已完全验证 REST `TIME_WINDOW`、默认 10 分钟 overlap、持久化业务 watermark、`LINK_NEXT` 多页拉取、分页循环/页数保护、分页中断不推进及通用 `source_record_id` 幂等。`CURSOR` 未实现；ACN 官方公网 REST 因无合法 Token 继续为 `BLOCKED_BY_ACCESS`。

| 类型 | 配置 | 连接测试 | 手动同步 | 定时同步 | 实时监听 | 自动重连 | 字段映射 | L1/L2/L3 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| FILE | 路径、映射、时区 | 是 | 是 | 否 | 不适用 | 不适用 | 是 | 共用管道 | 部分满足；属于人工文件导入 |
| REST_API | URL、Method、Header、TLS、认证、映射 | 是 | 是 | 是 | 否 | 不适用 | 是 | 共用管道 | 已实现轻量定时调度 |
| MQTT | Broker、Port、Topic、TLS、认证、映射 | 是 | 是 | 不适用 | 是 | 是 | 是 | 共用管道 | 已完全验证常驻订阅、退避重连与自动重新订阅 |
| THIRD_PARTY | 复用接口/文件配置 | 是 | 是 | 否 | 否 | 否 | 是 | 共用管道 | 部分满足；没有独立自动任务 |
| MANUAL | 记录、映射 | 是 | 是 | 否 | 不适用 | 不适用 | 是 | 共用管道 | 满足人工录入场景 |

## 真实校验规则

- L1 结构校验：必填字段、设备类型、时间解析、数值解析。
- L2 业务校验：指标支持、单位合法性与统一换算、非负/百分比范围。
- L3 时序校验：重复设备指标时间戳、未来时间戳、可配置变化率警告。
- 通过数据写入 `device_metric`；错误写入 `data_validation_log` 并隔离，警告数据保留 `WARNING` 质量标记。

当前没有缺失区间、时间间隔、设备/计量点业务关系的完整校验规则，也没有逐批同步历史表；页面不声称这些能力已完成。现有日志只记录错误/警告，不能重建每一级通过数，因此 API 返回 `passed: null`。

## 安全审计

- REST 默认要求 HTTPS，除非显式允许不安全连接；支持 TLS 校验。
- MQTT 支持 TLS、CA、客户端证书和用户名/密码配置。
- API 仅返回凭证是否已配置；password、token、secret、API key、证书私钥等字段脱敏。
- HTTP 或关闭 TLS 校验会在详情中显示为“安全传输未启用”，不会显示为安全。

## 自动采集结论

FastAPI lifespan 会启动 REST Scheduler 与 MQTT Subscription Manager，并在关闭时取消任务、断开客户端。REST 支持 15/30/60/360/1440 分钟周期、单源锁、120 秒超时和全局 4 路并发；MQTT 使用 1000 条有界队列，Paho 重连退避为 1–60 秒。两者均调用统一 `ingest_records` 校验/持久化管道。

自动化测试已验证调度触发、真实零、重复拒绝及 MQTT 消费管道。2026-08-25 使用 Docker `eclipse-mosquitto:2`（隔离端口 `18883`）和隔离 PostgreSQL 数据库 `carbon_neutral_p3_4_test` 完成真实集成验收：首次订阅和消息入库成功；强制停止 Broker 后运行状态进入 `RECONNECTING`；恢复同一 Broker 后无需人工 API 自动连接并在收到 SUBACK 后恢复 `RUNNING`；恢复后的新消息继续通过 Queue、consumer、`ingest_records`、L1/L2/L3 并写入 PostgreSQL。非法结构、非法单位和重复时序分别进入 L1、L2、L3 校验日志，Stop 后消息不再接收，FastAPI 重启后 enabled 数据源由 lifespan 自动恢复。MQTT 常驻监听、自动重连和自动重新订阅已完全验证。
