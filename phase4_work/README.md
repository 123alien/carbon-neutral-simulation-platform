# Carbon Neutrality Simulation Platform V1

最终验收 Demo 已补齐风电、充电桩、储能、空调、照明、第三方能源管理系统和用水的规则驱动自动采集模拟，并增加校园、公共机构及区域碳排案例。所有新增案例均标记为“示范仿真数据”。验收口径及 51 项状态见 [FINAL_ACCEPTANCE_51_TASKS.md](FINAL_ACCEPTANCE_51_TASKS.md)。

平台业务采用园区中心化结构。统一初始化流程、数据源关联和模型验证数据隔离规则见 [PARK_CENTERED_DATA_ACCESS.md](PARK_CENTERED_DATA_ACCESS.md)。

面向业务用户的八项一级菜单、主流程和碳中和仿真工作台结构见 [PLATFORM_INFORMATION_ARCHITECTURE.md](PLATFORM_INFORMATION_ARCHITECTURE.md)。

Current backend: V1.0.0-alpha.11; frontend: V1.0.0-beta.15; database revision: `020_long_term_path`.

## 正式报告输出

报告中心生成的 DOCX/PDF 已采用正式项目交付版式。正文只读取 `report_snapshot` 冻结数据，并以中文工程叙述、正式表格和打印型图表呈现；场景版本、仿真任务、模型版本和参数快照等技术信息仅在附录追溯。DOCX 与 PDF 使用同一渲染内容，PDF 通过独立 LibreOffice 适配器转换。

## Unified demonstration park

The current product target is a coherent demonstration environment. PostgreSQL `carbon_neutral_dev` contains one business park named **智慧低碳示范园区**, explicitly marked `DEMO_SIMULATION` / “示范仿真数据”. Its four buildings, seven energy systems, devices, meters, 8784-hour series, accounting, scenarios, carbon market, risks and frozen DOCX/PDF report all share one deterministic dataset. See [DEMO_DATA_DESIGN.md](DEMO_DATA_DESIGN.md).

### MQTT 光伏逆变器实时采集演示

实时 MQTT 数据仅验证自动采集能力，与全年仿真快照隔离。先在开发数据库幂等创建数据源和绑定对象：

```powershell
$env:APP_ENV='development'
$env:DATABASE_URL=$env:DEV_DATABASE_URL
python scripts/configure_mqtt_demo_pv.py
```

启动 FastAPI 后，数据源会由 lifespan 自动恢复常驻订阅；也可调用 `POST /api/data-sources/{id}/start`。随后启动设备模拟器：

```powershell
python scripts/mqtt_demo_pv_device.py
```

默认使用 EMQX 公共 Broker 的 TLS 8883 和专用 Topic `carbon-demo/cn-platform-7f3a/DEMO-PARK-001/pv/PV-INV-001/telemetry`。开发网络不支持 TLS 时可使用 `--no-tls --port 1883`；用 `--abnormal` 可验证缺字段、负功率、过温和重复时间戳隔离。公共 Broker 只允许发送脚本生成的非敏感演示数据。

Rebuild or refresh the demo case deliberately with:

```powershell
$env:DEMO_MODE='1'
$env:DATABASE_URL=$env:DEV_DATABASE_URL
python scripts/seed_demo_platform.py
```

The initializer refuses databases whose URL does not contain `carbon_neutral_dev`. Demonstration values are never labelled as real enterprise measurements.

P3-5.2.1 adds REST `TIME_WINDOW` incremental collection, persisted business watermark, configurable overlap (default 10 minutes), `LINK_NEXT` pagination and generic third-party record idempotency without changing `DeviceMetric`. See `REST_INCREMENTAL_ACQUISITION.md`.

P3-5 first-round real-public validation is documented under `real_public_datasets/`: five BDG2 Rat buildings, NASA POWER hourly weather, the matching-year US EPA eGRID2016 factor, plus separately stored China 2024 official electricity carbon-footprint factors and Hubei time-of-use policy. Observations, model outputs and unvalidated economics are explicitly separated; see `real_public_datasets/REAL_PUBLIC_IMPORT_REPORT.md`.

P3-5.2 adds an independent ACN Caltech EV Validation Site from the ACN-Data author's static export. The official REST API requires a registered Token and returned 401 without credentials, so FILE-based real-data validation is complete while official REST scheduling remains `BLOCKED_BY_ACCESS`. See `real_public_datasets/ACN_IMPORT_AND_REST_VALIDATION_REPORT.md`. Opt-in official integration runs only with `RUN_REAL_PUBLIC_ACN=1` and `ACN_API_TOKEN`; neither value is logged or committed.

## Data operating mode

Normal development uses local PostgreSQL. The current demonstration build may be populated only by the explicit initializer above; future real business data must still enter through the platform's park/building/device configuration and file, REST API, MQTT, third-party or manual data-source workflows. The browser frontend only calls FastAPI and never connects to PostgreSQL directly.

The deterministic generator remains guarded by `ALLOW_SYNTHETIC_VALIDATION=1`; the top-level demo initializer sets this guard only after `DEMO_MODE=1` and the development database-name check pass.

Before importing business data, maintain [REAL_DATA_INVENTORY.md](REAL_DATA_INVENTORY.md). It records ownership, authorization, time range, granularity, units, import readiness and known gaps without inventing missing values.

## Database environments

Database access belongs exclusively to FastAPI. The browser frontend only calls HTTP APIs.

| Environment | `APP_ENV` | Database | Purpose |
|---|---|---|---|
| Development | `development` | Local PostgreSQL `carbon_neutral_dev` | Normal development and real-data integration |
| Test | `test` | `test_*.db` selected by pytest modules | Backend automated tests |
| E2E | `e2e` | `frontend_smoke.db` | Playwright/smoke only |
| Production | `production` | Required PostgreSQL `DATABASE_URL` | Deployment; no fallback |

PostgreSQL is mandatory for development and production. SQLite is reserved for isolated automated tests. Development credentials are stored in the Windows user `DEV_DATABASE_URL` environment variable and must never be committed or printed.

One-time local PostgreSQL setup (Docker Desktop must be installed):

```powershell
.\scripts\setup-postgres-dev.ps1
```

This creates the local-only `carbon-neutral-postgres` container, persistent `carbon_neutral_pgdata` volume, `carbon_neutral_dev` database and `carbon_app` account, then runs Alembic to head. It does not import any business or synthetic data.

Development startup from the repository root:

```powershell
.\scripts\start-dev.ps1
```

`start-dev.ps1` refuses SQLite, starts the existing local PostgreSQL container when needed, and obtains the password-bearing URL from the user environment without logging it.

Frontend development startup:

```powershell
cd frontend
npm run dev
```

E2E uses its isolated backend and must never reuse port 8000:

```powershell
.\scripts\start-e2e-backend.ps1
cd frontend
$env:VITE_PROXY_TARGET='http://127.0.0.1:8001'
npm run dev
npm run e2e
```

Production must set `APP_ENV=production` and an explicit `postgresql+psycopg://...` URL. Application startup logs only environment, database type, database name/path and Alembic revision; credentials and complete URLs are never printed.

## Frontend V1.0.0-beta.14 / P3-3

P3-4 后端版本为 V1.0.0-alpha.9，数据库 revision 为 `016_p3_4`。REST 数据源可配置 15/30/60/360/1440 分钟后台采集；MQTT 数据源可启动常驻订阅。运行状态与启停入口位于 `/system/data-sources`。自动采集服务随 FastAPI lifespan 启停，所有消息继续通过统一字段映射、标准化和 L1/L2/L3 管道。

数据接入链路已在 `/data`、`/system/data-sources` 和 `/system/data-quality` 显性化。当前 REST API 与 MQTT 数据源均支持连接测试和手动同步，并共用字段映射、单位标准化、L1/L2/L3 校验及隔离管道；当前没有 REST 定时调度器或 MQTT 常驻监听/自动重连服务，界面会如实提示该能力缺口。详细审计见 `DATA_ACQUISITION_CAPABILITY_AUDIT.md`。

## Frontend V1.0.0-beta.13 / P2-13

P2-13 reorganizes the product into business workbenches, topic analysis and system management. It adds persistent real sidebar collapse, route-synchronized closable tabs, actionable administrator menus, visible Site context, an isolated setup flow, assessment/report workspace, interaction audit and Playwright interaction tests.

The completed productization pass also separates the four system-management responsibilities into independent routes, converts Data Access into a six-step Chinese business workflow, standardizes setup navigation and inline failures, and changes the simulation workspace to a focused measure selector with visible Site/ScenarioVersion/SimulationTask/time context and real recommendation, comparison and report handoffs.

## Frontend V1.0.0-beta.12 / P2-12

P2-12 upgrades Data Center from read-only browsing to an initialization and ingestion workflow: Site, Building, EnergySystem, Device, MeteringPoint and DataSource creation; FILE/REST/MQTT configuration with credential masking; field mapping; load/weather/price/grid-factor preview and confirmation; and a quality-to-accounting/simulation handoff. Preview never writes data.

## Frontend V1.0.0-beta.11 / P2-11

P2-11 adds a shared Three.js spatial engine to `/screen` and `/3d`: validated Site-centred coordinates, Site/Building/Device drill-down, carbon/energy/device layers, hourly task timeline, device telemetry details, NO_DATA rendering and deterministic WebGL cleanup. No coordinates or business values are fabricated.

## Frontend V1.0.0-beta.10 / P2-10

The standalone `/screen` route delivers a dark operational big screen without the ordinary
application shell. It reuses existing Site, carbon, hourly simulation, recommendation, batch,
market, risk and system APIs across independently degradable panels, a replaceable spatial
overview and nine high-value charts. Business facts refresh every 120 seconds and system facts
every 60 seconds with timer cleanup on unmount and Site changes. Frontend is V1.0.0-beta.10;
backend remains V1.0.0-alpha.8 and database head remains `015_p1_8`.

## Frontend V1.0.0-beta.9 / P2-9

The System Operations workspace at `/system` provides real backend/database/revision health,
redacted DataSource status and actions, Provider dynamic/fallback disclosure, registered model
capabilities, recent cross-domain tasks, runtime alerts, safe configuration and two read-only
traceability chains. New backend endpoints aggregate existing facts only and never expose
credentials, connection strings or private keys. Frontend is V1.0.0-beta.9; backend remains
V1.0.0-alpha.8 and database head remains `015_p1_8`.

## Frontend V1.0.0-beta.8 / P2-8

The Report Center at `/reports` creates feasibility-report tasks from a selected immutable
ScenarioVersion and matching SimulationTask, previews only the frozen ReportSnapshot, renders
DOCX/PDF through the existing backend renderers and downloads files through API endpoints.
Historical tasks expose status, failure reason, report number, snapshot provenance, SHA-256,
file size and generation time. Snapshot-derived chapter and chart previews never query current
source state as a replacement. Frontend is V1.0.0-beta.8; backend remains V1.0.0-alpha.8.

## Frontend V1.0.0-beta.7 / P2-7

The Carbon Market workspace at `/carbon-market` presents immutable market parameters,
real market-indicator trends, allowance/CCER/green-certificate analysis, frozen carbon-cost
assessments and batch scenario comparisons. The Risk workspace at `/risks` presents the six
backend-defined risk categories, distribution, detail, advice, history and scenario comparison.

Both workspaces accept ScenarioVersion and SimulationTask deep links, preserve missing-data
semantics and link successful assessments to the report route. P2-7 adds only read-only lists,
market time-series records and frozen batch-market comparison adapters. CarbonCostEngine,
RiskAssessmentEngine, database schema and backend V1.0.0-alpha.8 remain unchanged.

## Frontend V1.0.0-beta.6 / P2-6

The Scenario workspace at `/scenarios` manages formal scenarios, immutable version timelines,
complete parameter snapshots, copy-on-write version creation, multi-version SimulationBatch
execution and backend-authored 13-metric comparison. Recommendation provenance links back to
the original run, while every version links to version-bound hourly simulation.

P2-6 adds only read adapters for recent batches, existing Scenario creation timestamps and
market/risk snapshot fields already stored on ScenarioVersion. It does not change batch order,
comparison formulas, the hourly engine or database schema. Frontend is V1.0.0-beta.6; backend
remains V1.0.0-alpha.8.

## Frontend V1.0.0-beta.5 / P2-5

The Low-Carbon Path Recommendation workspace at `/recommendations` provides the complete
target-to-scenario flow: Site goals, selectable profiles, backend-default or custom weights,
candidate constraints, real recommendation execution, persisted history, validated Top-N
paths, score charts and immutable recommendation-to-scenario conversion.

Recommendation reasons, scores and hourly validation facts are rendered directly from the
backend response. P2-5 adds only a read-only recommendation-run list and persists the score
dimensions already produced by the existing engine. No algorithm, database schema or scenario
immutability semantics changed. Frontend is V1.0.0-beta.5; backend remains V1.0.0-alpha.8.

## Frontend V1.0.0-beta.4 / P2-4

The Simulation Workbench at `/simulation` now supports Site/scenario/version selection,
hourly and annual execution, load/weather quality inspection, seven unified measure cards,
Provider/fallback disclosure, validation, confirmation and result visualization. Immutable
scenario snapshots are loaded as configuration sources; hourly edits are submitted only as
temporary task snapshots and never update a historical version.

P2-4 adds weather-site discovery and optional temporary-measure/weather-site selection to the
existing hourly request adapter. The original hourly engine, physical balance order, device
models and database schema remain unchanged. Frontend is V1.0.0-beta.4 and backend remains
V1.0.0-alpha.8.

## Frontend V1.0.0-beta.3 / P2-3

The Carbon Management page at `/carbon` visualizes the existing P1-2 accounting facts by
Site, organization, Scope, energy type and day/month/year period. It includes overview cards,
Scope and energy composition/trends, organization comparisons, accounting-run history and
expandable emission-factor traceability without reproducing accounting formulas in the UI.

P2-3 adds one read-only run-list endpoint and optional filters to existing result/statistics
queries. These changes do not alter the accounting engine, database schema or historical
facts. The frontend is V1.0.0-beta.3; the backend remains V1.0.0-alpha.8.

## Frontend V1.0.0-beta.2 / P2-2

The Data Center at `/data` now provides seven coordinated workspaces for Site, Building,
EnergySystem, Device, MeteringPoint, DataSource and data quality. It consumes the existing
P1-7 APIs without duplicating ingestion or storage logic, keeps filters in page-local state,
and preserves the selected Site through `siteStore` and Dashboard deep links.

All lists and details distinguish real zero values from unavailable data. Energy, carbon,
telemetry, metering and quality charts reuse `BaseChart`; loading, empty, recoverable error
and retry states use the shared UI components. The frontend version is V1.0.0-beta.2 while
the backend remains V1.0.0-alpha.8.

## Frontend V1.0.0-beta.1 / P2-1

The independent `frontend/` application provides the Vue 3 + Vite + strict TypeScript
foundation. It uses Element Plus, Pinia, Vue Router, Axios and ECharts with a unified
research/management layout, eleven lazy module routes, normalized API errors and reusable
loading, empty, error, chart, table, status and statistics components.

The Dashboard calls the real `/health`, `/api/sites` and Site Overview endpoints. Missing
records are displayed as `暂无数据`; no demonstration metrics are embedded.

```bash
cd frontend
npm install
npm run dev
npm run build
```

Development proxies `/health` and `/api` to `http://localhost:8000`. Set
`VITE_API_BASE_URL` for direct API access in deployed environments.

## Run
```bash
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload
```
Swagger: http://127.0.0.1:8000/docs

## Simulation modes
- Annual: `/api/simulation/run` for long-horizon carbon-neutrality pathways.
- Hourly: `/api/simulation/hourly/run` for 8760-hour electricity/PV/efficiency energy balance.

## Hourly data workflow
1. Create enterprise.
2. Create scenario and configure PV/HVAC/LIGHTING measures.
3. Add electricity emission factor (`kgCO2/kWh`).
4. Upload hourly records via `/api/loads/hourly/bulk`.
5. Run `/api/simulation/hourly/run`.
6. Query stored hourly result using returned task id.

## CSV/Excel hourly import
Use the two-stage multipart API. Preview never writes to the database; confirmation
re-parses and re-validates the uploaded file before one transactional bulk insert.

- `POST /api/loads/hourly/import/preview`: file plus an `options` JSON form field.
- `POST /api/loads/hourly/import/confirm`: the same file and options after preview passes.
- Supported files: UTF-8 CSV, XLSX and XLSM.
- Field mapping supports timestamp, load, irradiation, temperature and humidity columns.
- Load units `W`, `kW` and `MW` are normalized to `load_kw`. Interval energy is derived
  into `load_kwh` for the existing simulation engine.
- Naive timestamps are interpreted in the supplied IANA timezone and stored as UTC.
- Confirmation is rejected for invalid values, timestamp gaps/irregularity, duplicates
  within the file, or timestamps already present for the enterprise.

Example `options` value:

```json
{"enterprise_id": 1, "mapping": {"timestamp": "time", "load": "power_kw", "irradiation": "ghi"}, "load_unit": "kW", "timezone": "Asia/Shanghai", "interval_minutes": 60, "source": "meter-export"}
```

## Hourly load query and statistics

All stored timestamps remain UTC. Query boundaries without an offset are interpreted in
the requested IANA `timezone`; returned timestamps and aggregation buckets use that zone.

- `GET /api/loads/hourly`: raw points by enterprise and `[start, end)` range.
- `GET /api/loads/aggregate`: `hour`, `day`, `month` or `year` buckets.
- `GET /api/loads/statistics`: energy, peak/average/minimum load, peak-valley difference,
  load factor and completeness for the whole range.
- `GET /api/loads/data-quality`: expected/observed/missing counts and explicit gap ranges.

Required query parameters are `enterprise_id`, `start` and `end`. Optional parameters are
`timezone` (default `UTC`) and `interval_minutes` (default `60`). Aggregation also accepts
`granularity`. Missing points are never interpolated: buckets are marked `COMPLETE`,
`PARTIAL` or `MISSING`.

## Weather and solar irradiance provider

Weather observations are attached to an enterprise through a weather site and stored as
UTC. `WeatherProvider` isolates the hourly engine from the physical data source; the
current database provider can later be supplemented by external APIs without changing the
simulation engine.

- `POST /api/weather/sites`: create a site with an IANA timezone.
- `POST /api/weather/import/preview` and `/confirm`: two-stage CSV/XLSX import.
- `GET /api/weather/hourly`: timezone-aware observations.
- `GET /api/weather/statistics`: temperature, humidity and GHI statistics.
- `GET /api/weather/data-quality`: completeness and explicit missing ranges.

Required weather fields are timestamp, temperature, humidity and GHI. DNI, DHI, wind
speed and cloud cover are optional. During hourly simulation, database GHI and temperature
override values embedded in the load profile at matching UTC timestamps. PV output uses
hourly GHI plus an ambient/cell-temperature correction; unmatched timestamps retain the
load-profile fallback and are recorded in the task snapshot.

## V0.8 hourly PV and storage

PV remains backward compatible: configurations without `irradiance_mode` use measured
GHI exactly as before. New PV parameters include:

- `irradiance_mode`: `GHI` or `POA`;
- `tilt_deg`, `azimuth_deg` and optional `poa_transposition_factor`;
- `inverter_efficiency`, `noct_c` and `temperature_coefficient_per_c`;
- optional `export_limit_kw`; surplus above the limit is explicit curtailed energy.

`POA` mode accepts explicit POA input when a provider supplies it, otherwise the V1
orientation transposition converts the current-hour GHI without forecasts.

Add storage as a normal scenario measure with `measure_type: "STORAGE"`. Parameters are
`capacity_kwh`, `max_charge_kw`, `max_discharge_kw`, `charge_efficiency`,
`discharge_efficiency`, `soc_initial`, `soc_min`, `soc_max`, and `strategy`. SOC values are
fractions of capacity. Strategies are `PV_SELF_CONSUMPTION` and
`PEAK_VALLEY_ARBITRAGE`; the latter accepts `peak_hours`, `off_peak_hours`, and optional
peak/off-peak/shoulder prices.

The hourly order is savings -> PV -> storage -> grid -> carbon -> economics. Results now
include storage charge/discharge, ending SOC, curtailed PV and the per-hour energy-balance
error. Dispatch uses only the current timestamp, current load/GHI and current SOC. Charging
and discharging cannot occur together, and SOC/power limits are enforced every hour.

## V0.9 dynamic electricity market and green power

Hourly simulation resolves market data in this order: database Provider value at the UTC
timestamp, then the existing fixed request/peak-valley value. Dynamic grid factors take
priority over the annual regional factor; the annual factor is required only for uncovered
timestamps.

- Price import: `/api/market/prices/import/preview` and `/confirm`.
- Grid-factor import: `/api/market/grid-factors/import/preview` and `/confirm`.
- Queries: `/api/market/prices` and `/api/market/grid-factors`.
- Contracts: `POST/GET /api/market/green-power/contracts`.

Imports support CSV/XLSX, field mapping, IANA timezone normalization, duplicate reporting
and confirmation-only persistence. A green contract may define a purchase share and/or a
finite kWh volume, lifecycle timestamps, contract emission factor and premium. Allocation
never exceeds physical grid imports and therefore does not alter energy conservation.

The full hourly order is savings -> PV -> storage -> grid -> green allocation -> dynamic
carbon -> dynamic-price economics. Hourly results expose the resolved purchase/feed-in
prices, resolved grid factor, green energy, green emissions and avoided carbon.

## V1.0.0-alpha.1 unified data-source adapters

`DataSourceAdapter` provides one ingestion pipeline for `FILE`, `REST_API`, `MQTT`,
`THIRD_PARTY` and `MANUAL` sources. Existing CSV/Excel load, weather and market endpoints
remain compatible; new integrations should use adapters. Supported device types are
electric/water/gas meters, PV, wind, EV chargers, storage, HVAC and lighting.

Pipeline: extract -> secure transport -> field mapping -> canonical unit conversion ->
L1 schema validation -> L2 semantic/range validation -> L3 temporal validation -> valid
metric persistence or validation-log quarantine. Bad records never enter `device_metric`.

REST sources require HTTPS unless development-only `allow_insecure` is explicitly set.
MQTT exposes TLS CA/client-certificate, broker authentication, topic and certificate
verification configuration. Put tokens, passwords, authorization headers and certificate
credentials in the `credentials` request field, not `config_json`. Credentials are encrypted
at rest and never returned. Set `DATA_SOURCE_SECRET_KEY` to a valid Fernet key in production.

Key endpoints:

- CRUD: `/api/data-sources` and `/api/data-sources/{id}`
- Connection/sync: `/api/data-sources/{id}/test` and `/sync`
- Quality: `/api/data-sources/{id}/data-quality`
- Devices: `POST/GET /api/devices`
- Metrics: `GET /api/devices/{id}/metrics`

Canonical metrics currently include `power_kw`, `energy_kwh`, `water_m3`, `gas_m3`,
`temperature_c`, `humidity_pct`, `irradiance_w_m2` and `soc_pct`. Adapter `field_mapping`
maps source fields to the standard record contract.

## V1.0.0-alpha.2 dynamic carbon accounting

`CarbonAccountingModel` and its registry separate activity normalization from factor
resolution and calculation. The initial energy model supports electricity, natural gas,
coal, oil and purchased heat. Electricity and heat default to Scope 2; combustion fuels
default to Scope 1. Explicit scope overrides remain subject to the run boundary.

Every persisted result contains original and canonical activity data, factor value/unit,
source, version, formula, standard basis and tCO2 result. Electricity reuses the existing
dynamic grid-factor Provider first and the existing regional annual factor resolver as
fallback. Other fuels reuse the same annual resolver; no second factor subsystem exists.

Organization nodes support `ENTERPRISE`, `BUILDING_PARK` and `REGION` levels. Activities
may reference both organization and device. Results can be filtered and aggregated by
day/month/year and split by energy, device, organization or scope.

Key endpoints:

- `POST/GET /api/organizations`
- `POST /api/carbon-accounting/runs`
- `GET /api/carbon-accounting/runs/{id}`
- `GET /api/carbon-accounting/runs/{id}/results`
- `GET /api/carbon-accounting/runs/{id}/statistics`

## V1.0.0-alpha.3 wind and EV charging

`HourlyDeviceModelRegistry` now exposes registered `WIND` and `EV_CHARGER` models through
`GET /api/simulation/hourly/models`. Both remain normal scenario measures with active
start/end years.

Wind uses the measured `weather_timeseries.wind_speed_m_s` at each UTC timestamp. Required
parameters are rated power and cut-in/rated/cut-out speeds. The model supports either the
default cubic/rated curve or a piecewise `power_curve` containing wind-speed and power-
fraction points.

EV charging supports charger count, per-charger rated power, utilization, daily energy,
charging start/end or arrival/departure hours, including overnight windows. A 24-value
`load_curve` can replace the uniform time-window rule. Daily requested energy is always
capped by available charging power.

Charging is added to system load before renewable/storage/grid balance but is not reduced
by HVAC or lighting measures. PV and wind form total renewable supply before storage.
Results retain separate PV/wind generation, self-use and export fields plus charging load,
total renewable generation/export and renewable curtailment. The same hourly conservation
check now includes wind generation and charging demand.

## V1.0.0-alpha.4 low-carbon path recommendations

`LowCarbonPathRecommendationEngine` builds a unified candidate library for PV, wind,
storage, HVAC, lighting, EV charging and green power. Rules derive initial sizes and
technical applicability from enterprise area/population plus measured load, irradiance and
wind. Candidate parameters and profile weights can be overridden per request.

Every candidate is independently validated by the existing `HourlySimulationEngine` using
the existing weather, price and factor Providers. Recommendation never creates simulation
tasks or changes historical simulation results. Only recommendation snapshots and validated
summaries are persisted.

Scores include reduction potential, investment, payback, technical applicability and target
satisfaction. Budget is a hard candidate constraint. Targets may include peak/neutral years,
carbon quota and grid-energy target. The API returns Top-N `ECONOMIC`, `REDUCTION` and
`BALANCED` profiles with reasons, measure configurations, reduction, investment, payback,
target satisfaction and engine-validation evidence.

- `POST /api/recommendations/low-carbon-paths`
- `GET /api/recommendations/low-carbon-paths/{run_id}`

## V1.0.0-alpha.5 scenario versions and simulation batches

Scenarios now have an identity plus immutable `ScenarioVersion` snapshots. Creating or
editing a scenario always appends a version and updates only the current-version pointer;
historical snapshots have no update API. Supported scenario types are `BASELINE`,
`ECONOMIC`, `REDUCTION`, `BALANCED` and `CUSTOM`.

Annual and hourly tasks bind `scenario_version_id` and embed the complete version snapshot
inside `parameter_snapshot_json`. Explicit historical versions execute from their stored
snapshot rather than the scenario's current projection.

`SimulationBatch` submits multiple versions for isolated sequential execution by the
existing hourly engine. Every item owns a different task id and result set. Comparison
includes carbon, reduction/rate, grid energy, renewable generation/self-consumption,
storage flows, electricity cost, investment, payback, target satisfaction and maximum
energy-balance error. Each numeric metric includes absolute and percentage change from the
selected baseline version.

Recommended paths can be copied into formal versioned scenarios. Conversion records the
source recommendation on the new version and never updates the recommendation itself.

- `POST/GET /api/scenarios/{id}/versions`
- `GET /api/scenarios/{id}/versions/{version_id}`
- `POST/GET /api/simulation/batches`
- `POST /api/recommendations/paths/{id}/convert-to-scenario`

## V1.0.0-alpha.6 carbon-market scenario, risk and report data

Carbon-market parameters are bound one-to-one to immutable scenario versions and copied
into simulation parameter snapshots. `CarbonCostEngine` calculates quota balance, excess
cost, CCER offsets/cost, green-certificate cost, net emissions and comprehensive carbon
cost as a financial/accounting overlay; it never changes the physical energy balance.

`RiskAssessmentEngine` returns level, indicator, trigger and recommendation for peak and
neutrality delay, payback, electricity/carbon price volatility, renewable variability and
technical implementation. `ReportEngine` combines accounting, recommendations, batch
comparisons, carbon-market assessments and risks into versioned structured report data
ready for a later Word/PDF renderer.

Database persistence uses `carbon_market_scenario`, `carbon_market_timeseries`,
`risk_assessment_run`, `risk_assessment_result`, `report_task` and `report_snapshot`.
Both scenario versions and simulation tasks carry independent frozen market/risk snapshot
columns. Cost, risk and report records require matching scenario-version and simulation-task
foreign keys; assessments always read the task snapshot rather than current market state.

- `POST/GET /api/carbon-market/scenarios`
- `POST /api/carbon-market/indicators/bulk`
- `GET /api/carbon-market/statistics`
- `POST/GET /api/carbon-market/assessments`
- `POST/GET /api/risk-assessments`
- `POST/GET /api/reports/feasibility`

## V1.0.0-alpha.8 formal DOCX/PDF reports

P1-8 renders formal carbon-neutrality feasibility and risk reports exclusively from the
immutable `report_snapshot`. `DocxReportRenderer` and `PdfReportRenderer` implement a
shared adapter contract and consume the same frozen input; rendering never re-queries
mutable scenario, accounting, simulation, recommendation, market or risk state.

Reports contain the required cover and analytical sections, a TOC, headers, footers, page
fields, traceability metadata, explicit units, tables and nine snapshot-driven charts.
Missing chart series are labeled as unavailable rather than replaced with demonstration data.
Artifacts are recorded in `report_file` with format, filename, storage path, size, SHA-256
checksum and generation time, unique by report and format.

- `POST /api/reports/{id}/render`
- `GET /api/reports/{id}/downloads`
- `GET /api/reports/{id}/download/docx`
- `GET /api/reports/{id}/download/pdf`

## Hourly input semantics

## V1.0.0-alpha.7 localized business data API

P1-7 adds a business-facing `Site -> Building -> EnergySystem -> Device/MeteringPoint`
view for parks, campuses, public institutions, enterprises and streets. It does not add a
second ingestion, device, telemetry or carbon-accounting pipeline: metering and telemetry
read `device_metric`, carbon endpoints read P1-2 `carbon_accounting_result`, and quality
indicators retain the existing observed/missing semantics.

The `site`, `building`, `energy_system` and `metering_point` tables use restrictive or
nullifying foreign keys so deleting a business view cannot cascade into devices, telemetry,
accounting, simulation or scenario history. Coordinates and JSON geometry are optional
placeholders only; no 3D capability is implemented in P1-7.

- `POST/GET /api/sites`, `GET /api/sites/{id}/overview`
- `POST/GET /api/sites/{id}/buildings`
- `GET /api/buildings/{id}/overview|energy|carbon|devices`
- `POST/GET /api/energy-systems`, `GET /api/energy-systems/{id}/devices|metrics`
- `GET /api/sites/{id}/devices`, `GET /api/devices/{id}/overview|telemetry`
- `POST/GET /api/metering-points`, `GET /api/metering-points/{id}/timeseries`
- `GET /api/sites/{id}/carbon|carbon/statistics`

`load_kwh` means interval energy for one hour. `irradiation_wm2` is the average plane-of-array irradiance for that hour. In Phase 4 the PV model uses:
`PV_kWh = capacity_kW * irradiation_Wm2 / 1000 * performance_ratio * degradation_factor`.
For real datasets, normalize timestamps, timezone, missing values and interval units before import.

## Tests
```bash
pytest -q
```

## Database migrations
Schema changes are managed only through Alembic. Set `DATABASE_URL` for PostgreSQL,
then run `python -m alembic upgrade head`. To verify rollback locally, run
`python -m alembic downgrade base` against a disposable database.
