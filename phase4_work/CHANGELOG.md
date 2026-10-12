# Changelog

## 2026-09-05 最终验收 Demo 补齐

- 新增五类设备、第三方能源管理系统和用水的规则驱动 REST 自动采集模拟。
- 新增校园、公共机构和区域碳排放汇总案例。
- 新增 GB/T 32150-2015 完整映射及可复算核算逻辑验证。
- 数据接入与碳核算页面增加自动采集、用水、区域排名和标准验证展示。
- 所有新增数据统一标识为“示范仿真数据”，不恢复已删除公开数据集。

## 正式项目报告模板重构

- DOCX/PDF 报告改为正式中文项目交付风格，正文按概述、基础数据、目标、低碳路径、仿真、措施评估、风险、结论和附录九章组织。
- 移除正文中的 JSON、数据库字段、英文枚举和内部任务标识；技术追溯信息统一收口至附录。
- 统一 A4 版式、宋体正文、黑体黑色标题、1.5 倍行距、居中页码、页眉和打印友好的灰阶图表。
- DOCX 与 PDF 由同一冻结报告快照和同一版式生成，历史源数据变化不会改变报告内容。
- 新增可见目录、多场景对比、投资与回收期双轴图和风险等级汇总图，并完成 14 页逐页渲染检查。

## 统一示范园区全链演示

- 新增“智慧低碳示范园区”，包含4栋建筑、7类能源系统、12台设备、9个计量点和8个示范数据源。
- 新增确定性全年8784小时负荷、气象、光伏、风电、储能、充电桩、电价和动态排放因子生成逻辑。
- 打通园区管理、数据接入、碳核算、3D全景、四场景仿真、碳市场、风险和DOCX/PDF报告。
- 所有示范数据统一标记为 `DEMO_SIMULATION`，前端显示“示范仿真数据”，不冒充真实企业实测数据。
- 园区碳排查询改为最近一次成功核算快照，避免多次历史核算结果在当前看板重复累加。
- 公开模型验证文件缺失时报告明确显示不可用，不再阻断园区报告生成。

## 3D全景独立大屏

- `/3d` 从普通主布局中独立，进入后不显示业务侧栏、顶部页签和表单式页面框架。
- 新增园区三维场景、碳排总览、建筑排名、能源趋势、光伏/风电、储能、设备状态和告警联动面板。
- 时间范围、建筑、设备和指标支持交互，并可返回碳核算、碳中和仿真或业务平台。
- 所有面板共享当前园区和同一仿真任务数据；缺失数据明确显示“暂无数据”，不生成互相矛盾的演示值。

## 园区管理与数据接入解耦

- 园区、建筑、能源系统、设备和计量点统一在园区管理内创建与配置。
- 数据接入收敛为接入对象、数据源、数据采集/导入、数据质量结果四步流程。
- 删除旧数据中心初始化页面和七步初始化向导，历史 `/data?setup=1` 兼容重定向到园区创建。
- 首页、大屏和三维全景的无园区入口统一指向园区管理。
- 后端业务接口、历史数据和三级质量校验能力保持不变。

## 园区业务信息架构重组

- 左侧导航收敛为综合首页、园区管理、数据接入、碳核算、3D全景、碳中和仿真、碳市场、报告中心。
- 新增碳中和仿真统一工作台，串联基准、目标、推荐、全过程仿真、场景比较、参数调整和综合分析。
- 原推荐、场景、风险、系统运行和模型验证路由继续兼容，但不再机械拆成一级业务菜单。
- 园区管理整合园区、建筑、能源系统、设备和计量点，数据接入默认进入数据源流程。

## 园区中心化数据接入改造

- 正式业务园区与公开模型验证园区分类查询，业务选择器不再混入公开验证数据。
- 数据源增加园区、建筑、设备、计量点关联及文件数据性质。
- 数据接入工作台的数据源和质量汇总按当前园区查询。
- 保留既有适配器、三级校验和历史公开验证结果。

## Backend V1.0.0-alpha.11 / Frontend V1.0.0-beta.15 / P3-5.2.1

- Added verified REST `TIME_WINDOW`, persisted business watermark and 0–60 minute overlap.
- Added verified `LINK_NEXT`, relative/absolute Next support, 100-page default limit, record limit, loop detection and page failure diagnostics.
- Added `external_record_dedup` idempotency while preserving DeviceMetric temporal fallback.
- Added Chinese advanced REST configuration and runtime window/watermark/page/duplicate status.
- Added Alembic `017_p3_5_2_1`; ACN official REST remains `BLOCKED_BY_ACCESS` without a valid token.

## P3-5.2 / ACN-Data real EV validation (versions unchanged)

- Added a separate ACN Caltech EV Validation Site with 3 EVSE devices, 122 real sessions and 359,029 original samples.
- Imported 116 published session-energy facts through the FILE Adapter and existing L1/L2/L3 pipeline; six missing energy totals remain explicitly missing.
- Confirmed that the official ACN API requires a registered Token and that the current REST Adapter lacks ACN HATEOAS pagination and incremental windows.
- REST scheduler validation is marked `BLOCKED_BY_ACCESS`, not passed; no mock response is used as real-data evidence.
- Backend remains V1.0.0-alpha.10, frontend remains V1.0.0-beta.14, Alembic remains `016_p3_4`.

## Backend V1.0.0-alpha.10 / P3-5 first round

- Added the traceable `raw → cleaned → normalized → manifest → API → PostgreSQL` real-public validation chain.
- Imported 43,910 BDG2 observed facts, 5,709 common-complete hourly load points and 5,709 NASA POWER weather points.
- Completed matching-year eGRID2016 Scope 2 accounting and the hourly baseline simulation with zero maximum energy-balance error.
- Added frozen public-dataset classification, source, time range and limitations to report snapshots and DOCX/PDF output.
- Database schema is unchanged; Alembic remains `016_p3_4`.

## Real-data PostgreSQL development mode (versions unchanged)

- Switched normal development to a clean local PostgreSQL `carbon_neutral_dev` database with persistent local storage.
- Removed the SQLite development fallback and made development startup reject non-PostgreSQL URLs.
- Added repeatable local PostgreSQL setup without printing or committing generated credentials.
- Disabled synthetic case loaders by default and isolated them to an explicit test-only database.
- Preserved the former SQLite case database as an untouched validation archive; no synthetic records were migrated.

## P3-1 full-case validation (versions unchanged)

- Added a deterministic 2024 synthetic demonstration park dataset and idempotent API-based loader.
- Completed the accounting, four-scenario hourly batch, recommendation, carbon-market, risk and immutable DOCX/PDF report chain in the development database.
- Added read-only full-case browser validation artifacts and `FULL_CASE_VALIDATION_REPORT.md`.
- Fixed future timestamps being accepted by hourly-load import preview and added regression coverage.
- Kept Frontend V1.0.0-beta.13, Backend V1.0.0-alpha.8 and Alembic 015_p1_8.

## V1.0.0-beta.13 / P2-13

- Reorganized navigation into business workbenches, topic analysis and system management.
- Added real persistent sidebar collapse, route tabs, administrator dropdown, fullscreen and visible Site context.
- Isolated `/data?setup=1`, added evaluation/report workbench and formal interaction audit.
- Added Playwright coverage for navigation, administrator menu, tabs and setup mode.
- Split system objects, data sources, Providers and data quality into four independent management pages.
- Rebuilt Data Access as a six-step Chinese business workflow with actionable empty states.
- Standardized setup actions and inline failure feedback; Site creation advances automatically.
- Reworked the simulation measures into a focused selector and added visible business context plus real downstream handoffs.

## V1.0.0-beta.12 / P2-12

- Added empty-database SetupWizard and object creation workflow.
- Added FILE/REST_API/MQTT/THIRD_PARTY/MANUAL DataSource wizard with masked credentials.
- Added reusable field mapping plus load, weather, electricity price and grid-factor Preview/Confirm imports.
- Preserved backend V1.0.0-alpha.8 and database revision 015_p1_8.

## V1.0.0-beta.11 / P2-11

- Added shared Three.js scene, spatial validation/local-coordinate conversion and `/3d` panorama.
- Upgraded `/screen` central panel with 3D drill-down, layer legend, task timeline and explicit NO_DATA handling.
- Added telemetry details and renderer/listener/animation cleanup.

## V1.0.0-beta.10 / P2-10
- Added the standalone dark `/screen` carbon-neutrality operational big screen.
- Added Site-wide carbon, energy, measure, recommendation, scenario, market, risk and system panels.
- Added a replaceable two-dimensional CentralSpatialPanel for future P2-11 3D implementation.
- Added nine BaseChart visualizations without introducing new business calculations or fact tables.
- Added partial-request degradation, explicit no-data/fallback/unassessed semantics and Site refresh.
- Added 60-second system and 120-second business refresh timers with duplicate prevention and cleanup.
- Added browser Fullscreen API entry/exit and direct links to all underlying business workspaces.
- Preserved backend V1.0.0-alpha.8, database `015_p1_8` and every existing engine.

## V1.0.0-beta.9 / P2-9
- Added `/system` for platform health, version, database revision and operational status.
- Added redacted DataSource summaries, connection tests, supported manual sync and quality facts.
- Added Weather, electricity-price, grid-factor and green-power Provider dynamic/fallback disclosure.
- Added registered hourly model capabilities and recent simulation/recommendation/batch/risk/report tasks.
- Added runtime alerts for source failures, low quality, Provider fallback and failed tasks.
- Added read-only ScenarioVersion and DataSource business traceability chains.
- Added three operational charts and safe non-sensitive configuration display.
- Added read-only system aggregation endpoints without database or engine changes.

## V1.0.0-beta.8 / P2-8
- Added `/reports` with Site/scenario/version/task context and deep-link selection.
- Added report-input completeness summary and immutable snapshot creation.
- Added task history, status/failure display, trace chain and snapshot-only chapter preview.
- Added DOCX/PDF selection, backend rendering, current file metadata and API-based downloads.
- Added nine snapshot-derived report chart previews with explicit missing-data states.
- Added simulation-to-report and existing market/risk-to-report integration.
- Added a minimal filtered report-history endpoint exposing existing snapshots and file records.
- Preserved ReportEngine, renderers, checksums, database schema and backend V1.0.0-alpha.8.

## V1.0.0-beta.7 / P2-7
- Added `/carbon-market` with immutable market snapshots, indicator trends and assessment execution.
- Added allowance, CCER, green-certificate and comprehensive carbon-cost analysis without client-side recalculation.
- Added frozen batch carbon-market comparison and scenario/task/batch query deep links.
- Added `/risks` with all six backend risk categories, detail, advice, history and scenario comparison.
- Added risk-level and distribution charts while preserving “未评估” as distinct from low risk.
- Added scenario-to-market/risk and assessment-to-report links.
- Added minimal read-only assessment history, risk history, time-series records and batch comparison adapters.
- Preserved database schema, immutable snapshots and backend V1.0.0-alpha.8 calculation engines.

## V1.0.0-beta.6 / P2-6
- Added the `/scenarios` formal scenario portfolio with deep-link selection and five scenario types.
- Added immutable version timelines, full snapshots and copy-on-write new-version creation.
- Added recommendation source/profile/rank/score traceability and recommendation/simulation links.
- Added multi-version batch selection, explicit baseline rules, task/item status and partial failure display.
- Added the backend-authored 13-metric table, absolute deltas, change rates and nine comparison charts.
- Added a minimal recent-batch list and exposed existing Scenario/version snapshot timestamps and fields.
- Preserved database schema, version immutability, batch execution, comparison formulas and backend V1.0.0-alpha.8.

## V1.0.0-beta.5 / P2-5
- Added the `/recommendations` target-to-recommendation-to-scenario workflow.
- Added three profile views, backend-default/custom five-dimensional weights and candidate overrides.
- Added Site baseline context, real Loading/failure/empty states and persisted recommendation history.
- Added validated Top-N cards, backend reasons, measure parameters, target status and balance warnings.
- Added radar, reduction, investment, payback and reduction-investment comparison charts.
- Added formal scenario conversion and deep links to scenario management and version-bound simulation.
- Added a minimal read-only run list and persisted existing engine score dimensions without changing scoring.
- Preserved recommendation records, scenario-version immutability, database schema and backend V1.0.0-alpha.8.

## V1.0.0-beta.4 / P2-4
- Added the `/simulation` configuration-to-result workbench for annual and hourly simulation.
- Added unified MeasureCard configuration for PV, wind, storage, HVAC, lighting, EV charging and green power.
- Added load/weather completeness and dynamic Provider versus fallback disclosure.
- Added client-side boundary validation while retaining backend validation as authoritative.
- Added eight hourly result charts, task metadata, summary metrics and energy-balance warnings.
- Added snapshot-only temporary hourly measures and explicit weather-site selection without mutating scenario versions.
- Preserved the database schema, physical balance order, simulation models and backend V1.0.0-alpha.8.

## V1.0.0-beta.3 / P2-3
- Added the `/carbon` management workspace for overview, Scope, energy, trend, organization, factor and run analysis.
- Added five snapshot-free `BaseChart` visualizations backed by P1-2 and P1-7 query results.
- Added typed accounting run/result/statistics, organization and emission-factor trace models.
- Added Dashboard-to-carbon Site deep links and retained `siteStore` as the shared Site context.
- Added a minimal read-only accounting-run list endpoint and optional result/statistics filters.
- Preserved accounting formulas, factor units, historical facts, database schema and backend V1.0.0-alpha.8.

## V1.0.0-beta.2 / P2-2
- Added the `/data` Data Center with Site, Building, EnergySystem, Device, MeteringPoint, DataSource and quality workspaces.
- Added typed Building, energy-system and metering-point API modules and expanded existing Site, Device and DataSource clients.
- Added Site creation, hierarchy navigation, local filtering and Dashboard-to-Site deep links.
- Added snapshot-free real API views for energy/carbon trends, telemetry, metering data and quality metrics.
- Reused `BaseChart` for four chart families and shared loading, empty, error and retry states.
- Preserved real zero values, explicit units and `NO_DATA` semantics; backend remains V1.0.0-alpha.8.

## V1.0.0-beta.1 / P2-1
- Added the independent Vue 3, Vite and strict TypeScript frontend workspace.
- Added a unified navigation shell and eleven lazy module routes with 404 handling.
- Added normalized Axios API modules and Pinia app/site/scenario stores.
- Added reusable page, state, chart, table, statistic and status components.
- Added a real-API Dashboard with explicit empty and recoverable error states.
- Added proxy/environment configuration while retaining backend V1.0.0-alpha.8.

## V1.0.0-alpha.8 / P1-8
- Added snapshot-only formal DOCX and PDF report renderers behind a shared adapter contract.
- Added cover, TOC, traceability metadata, required sections and nine snapshot-driven charts.
- Added PENDING/GENERATING/SUCCESS/FAILED report task lifecycle and failure diagnostics.
- Added unique multi-format report artifacts with SHA-256 checksums and download APIs.
- Added reversible `015_p1_8` migration and rendering, download and immutability tests.

## V1.0.0-alpha.7 / P1-7
- Added Site, Building, EnergySystem and MeteringPoint business entities and localized APIs.
- Reused existing devices, device metrics, data sources, quality status and P1-2 accounting results.
- Added UTC/IANA telemetry and energy aggregation with explicit units and `NO_DATA` responses.
- Added site/building overview, energy, carbon, device and metering-point hierarchy queries.
- Reserved optional coordinates and JSON position/geometry fields without implementing 3D.
- Added `014_p1_7` reversible migration with foreign-key, index and constraint tests.

## V1.0.0-alpha.6 / P1-6
- Added immutable-version-bound carbon price, quota, CCER and green-certificate scenarios.
- Added a non-physical CarbonCostEngine for quota balance, offsets, net carbon and total cost.
- Added carbon-market indicator ingestion and statistics for price, quota, volume, CCER and certificates.
- Added six-category RiskAssessmentEngine output with triggers and recommendations.
- Added structured feasibility/risk report data combining accounting, recommendations and scenario batches.
- Copied carbon-market configuration into annual/hourly task snapshots without changing energy balance.
- Split risk runs/results and report tasks/snapshots, with mandatory scenario-version and simulation-task traceability.
- Added frozen market/risk snapshot columns plus Alembic upgrade/downgrade and snapshot-immutability coverage.

## V1.0.0-alpha.5 / P1-5
- Added immutable scenario versions for baseline, economic, reduction, balanced and custom paths.
- Bound annual/hourly tasks to version ids and complete parameter snapshots.
- Added isolated multi-version hourly simulation batches and baseline-relative comparison metrics.
- Added recommendation-to-scenario copying with source traceability and no recommendation mutation.

## V1.0.0-alpha.4 / P1-4
- Added rule-based candidate generation for all current low-carbon/device measures.
- Added configurable multi-objective economic, reduction and balanced scoring profiles.
- Added budget, quota, energy and peak/neutral target satisfaction scoring.
- Required every recommendation candidate to pass the existing hourly simulation engine.
- Added immutable recommendation input, score, reason and validation persistence without simulation-result mutation.

## V1.0.0-alpha.3 / P1-3
- Added registered hourly wind and EV-charging device models.
- Added measured-wind power curves with cut-in/rated/cut-out boundaries and active years.
- Added charger fleet, utilization, daily-energy, arrival/departure and 24-hour curve rules.
- Integrated charging as new demand and wind as renewable supply before storage/grid balance.
- Added persisted wind, charging, total renewable export and curtailment result fields.

## V1.0.0-alpha.2 / P1-2
- Added registered `CarbonAccountingModel` abstraction and canonical energy model.
- Added enterprise/building-park/region organization hierarchy and Scope 1/2 boundaries.
- Added traceable accounting runs/results with activity, factor, source, version, formula and standard basis snapshots.
- Reused dynamic grid and annual factor Providers for electricity, gas, coal, oil and heat.
- Added day/month/year statistics and energy/device/organization/scope splits.

## V1.0.0-alpha.1 / P1-1
- Added unified FILE/REST_API/MQTT/THIRD_PARTY/MANUAL `DataSourceAdapter` registry.
- Added REST HTTPS and MQTT TLS/authentication adapter interfaces.
- Added encrypted credential storage and recursively redacted API configuration responses.
- Added source, device, canonical metric and validation-log persistence.
- Added field/unit normalization, three-level validation, anomaly quarantine and quality reporting.
- Added data-source CRUD, connection test, sync, device and metric APIs.
- Preserved all existing specialized CSV/XLSX import endpoints.

## V0.9.0 / P0-6
- Added electricity-price and dynamic grid-factor Provider abstractions with database implementations.
- Added two-stage CSV/XLSX imports and range-query APIs for market time series.
- Added green-power contracts with share/volume allocation, lifecycle, emissions and premium cost.
- Prioritized hourly Provider values while preserving fixed price and annual-factor fallbacks.
- Extended hourly results with resolved prices/factors and green-power carbon accounting.

## V0.8.0 / P0-5
- Added extensible GHI/POA `SolarIrradianceModel`, orientation parameters and inverter efficiency.
- Preserved legacy GHI behavior and NOCT-based temperature correction.
- Added stateful hourly storage with PV self-consumption and peak-valley rule strategies.
- Integrated storage after PV and before grid/carbon/economics without future-data lookahead.
- Added charge, discharge, SOC, curtailment and balance-error result persistence.
- Added strict hourly energy-conservation, SOC, efficiency and power-boundary tests.

## V0.7.0 / P0-4
- Added weather sites and UTC weather observations with an Alembic migration.
- Added the WeatherProvider abstraction and database-backed provider.
- Added two-stage CSV/XLSX weather import with timezone, completeness and duplicate validation.
- Added hourly, statistics and data-quality weather APIs.
- Hourly PV simulation now prioritizes measured GHI and temperature and applies temperature derating.

## V0.6.0 / P0-3
- Added timezone-aware UTC range queries for hourly load data.
- Added hour/day/month/year aggregation in the requested display timezone.
- Added energy, load distribution, load factor and completeness statistics.
- Added explicit missing buckets and contiguous missing-interval quality reports without interpolation.
- Added API regression coverage for all four endpoints and granularities.

## V0.5.0 / P0-2
- Added two-stage CSV/XLSX hourly load import with field mapping and bounded preview.
- Added timezone-to-UTC normalization and W/kW/MW conversion to canonical `load_kw`.
- Added interval-energy derivation for backward-compatible hourly simulation.
- Added completeness, irregular interval, invalid value, in-file duplicate and database duplicate reports.
- Added confirmation-only transactional persistence and automated API coverage.

## V0.4.1 / P0-1
- Added Alembic configuration and versioned Phase 1-4 migrations.
- Added automated upgrade-to-head and downgrade-to-base migration coverage.
- Removed application-startup `Base.metadata.create_all`; startup now expects a migrated database.

## V0.4.0 / Phase 4
- Added hourly load/weather/irradiance profile storage (`load_timeseries`).
- Added deterministic hourly simulation engine with HVAC/lighting saving, PV generation, energy balance, carbon and electricity economics.
- Added `simulation_hour_result` persistence.
- Added bulk hourly profile API and hourly simulation API.
- Added PV self-consumption and load-coverage metrics.
- Kept annual simulation API unchanged for long-horizon 2025-2060 scenarios.

## V0.3.0 / Phase 3
- Canonical energy unit conversion.
- Dynamic emission-factor resolution by year/region.
- Automatic baseline growth estimation.
- Multi-scenario comparison API.
# V1.0.0-beta.14 / P3-3

- Added truthful acquisition overview and data-source detail APIs without changing database schema.
- Exposed protocol, security, bindings, field mapping, L1/L2/L3 validation logs and quarantined rows.
- Reworked data-source and data-quality pages; added concise Dashboard and big-screen acquisition status.
- Explicitly report that REST scheduling and MQTT persistent subscription/reconnect are not implemented.
- Added capability audit, requirement mapping and backend regression coverage.
# Backend V1.0.0-alpha.9 / P3-4

- Added lifespan-managed REST interval scheduler and persistent MQTT subscription manager.
- Added runtime configuration/state, start/stop/sync-now APIs, bounded MQTT queue, reconnect backoff, per-source REST locks and global concurrency control.
- Added Alembic `016_p3_4`; no business fact tables or existing facts were modified.
- Automatic REST/MQTT ingestion reuses the existing mapping, normalization and L1/L2/L3 pipeline.
- P3-4.1 verified real Mosquitto disconnect, bounded reconnect, automatic resubscription, post-recovery ingestion, L1/L2/L3 rejection, explicit stop and lifespan restoration against an isolated PostgreSQL database.
- Fixed Paho MQTT v2 `ReasonCode` callback compatibility and now marks subscriptions active only after a successful Broker SUBACK.
