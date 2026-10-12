# 多源自动采集与分级校验要求映射

| 技术要求 | 实现依据 | 状态 |
|---|---|---|
| 物联网设备支持 | PV、WIND、STORAGE、EV_CHARGER、HVAC、LIGHTING、电/水/气表；设备页中文分类 | 已完全满足（类型与台账） |
| 第三方系统 | REST_API、MQTT、THIRD_PARTY、FILE Adapter | 已部分满足（REST/MQTT 可自动运行；通用 THIRD_PARTY 仍需按实际协议配置） |
| 数据采集提取 | `DataSourceAdapter.extract`、`field_mapping`、标准单位换算 | 已完全满足手动触发链路 |
| 安全传输 | HTTPS 限制、MQTT TLS/证书/认证、凭证加密和响应脱敏 | 已完全满足配置与传输层要求 |
| 分级校验 | L1_SCHEMA、L2_SEMANTIC、L3_TEMPORAL、DataValidationLog、隔离 | 已部分满足（缺少缺失区间/计量点关系等规则） |
| 全流程同管道 | Source → Adapter → Mapping → L1/L2/L3 → DeviceMetric/ValidationLog → Data Quality | 已完全满足手动同步链路 |
| REST 定时自动采集 | lifespan Scheduler、持久配置、运行状态、单源锁与并发限制 | 已完全满足 |
| MQTT 常驻实时订阅/自动重连 | Subscription Manager、Paho loop、1–60 秒重连、有界 Queue、SUBACK 状态确认；2026-08-25 Docker Mosquitto 断线恢复测试 | 已完全验证（自动重连、自动重新订阅、恢复后统一校验入库） |
| 可追踪批次运行日志 | 最近同步、累计指标和校验日志可查；无独立同步批次表 | 已部分满足 |
| 原始数据预览 | 文件/Provider 既有 Preview；通用 REST/MQTT DataSource 无独立 raw preview API | 已部分满足 |

验收界面：`/data` 采集运行总览、`/system/data-sources` 自动采集配置/启停/轮询详情、`/system/data-quality` 三级校验及隔离记录、`/dashboard` 与 `/screen` 简要数据接入状态。

P3-4.1 集成验收使用独立 `eclipse-mosquitto:2` Broker 和 PostgreSQL 测试库，覆盖 `RUNNING → RECONNECTING → RUNNING`、自动 SUBACK、恢复后消息、L1/L2/L3 拒绝、Stop 隔离及 FastAPI lifespan 恢复；未向 development 数据库写入测试事实。
