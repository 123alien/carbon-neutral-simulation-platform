# Version History

- Database `019_park_centered_data_sources`: park/building/device/metering-point binding for data sources, file data nature, business/validation park separation.

## V1.0.0-alpha.11 / V1.0.0-beta.15

P3-5.2.1 completes verified REST time-window incremental acquisition, LINK_NEXT pagination, persisted watermark, overlap recovery and generic third-party record idempotency. Database head is `017_p3_5_2_1`. CURSOR and authenticated ACN public REST remain unverified.

## P3-5.2 data validation (versions unchanged)

ACN-Data real EV session validation added without application schema or production-code changes. Official REST integration remains access-blocked pending a user-issued ACN Token.

## V1.0.0-alpha.10

P3-5 first-round public real-data validation and report-provenance compatibility fix. Frontend remains V1.0.0-beta.14 and database revision remains `016_p3_4`.

## V1.0.0-beta.13

P2-13: frontend productization, workflow navigation, independent system-management responsibilities, Chinese data-ingestion flow, focused simulation workbench and real-interaction hardening. Backend remains V1.0.0-alpha.8; database head remains 015_p1_8.

## V1.0.0-beta.12

P2-12: system initialization, base object configuration and Provider data ingestion frontend workflow. Backend and database versions unchanged.

## V1.0.0-beta.11

P2-11: Three.js spatial visualization foundation and full panorama. Backend remains V1.0.0-alpha.8 and database remains 015_p1_8.

## V1.0.0-beta.10

P2-10 provides the comprehensive management screen for meetings and operational monitoring,
composing existing business facts into a dense dark visualization layout with partial failure
isolation, automatic refresh and fullscreen mode. Backend remains V1.0.0-alpha.8 at revision
`015_p1_8`; no backend or database change was required.

## V1.0.0-beta.9

P2-9 delivers the System Operations workspace with live health, Provider fallback visibility,
DataSource quality, task failure traceability, safe configuration and read-only business lineage.
Backend remains V1.0.0-alpha.8 at revision `015_p1_8`; no migration or business-engine change
was introduced.

## V1.0.0-beta.8

P2-8 delivers the formal Report Center over the existing immutable ReportSnapshot and
DOCX/PDF renderer pipeline. It provides frozen chapter/chart previews, task history, failure
visibility, file integrity metadata and API downloads. Backend remains V1.0.0-alpha.8 at
revision `015_p1_8`; no database migration or report-generation logic change was introduced.

## V1.0.0-beta.7

P2-7 exposes the existing carbon-cost and six-category risk engines through traceable market
and risk workspaces. Results remain bound to immutable ScenarioVersion and SimulationTask
snapshots, with historical lists, batch comparison and report deep links. Backend remains
V1.0.0-alpha.8 at revision `015_p1_8`; no database migration was added.

## V1.0.0-beta.6

P2-6 delivers formal scenario management, immutable parameter history, copy-on-write versions,
SimulationBatch submission and backend-authored baseline comparison across thirteen metrics.
Recommendation and simulation deep links complete the cross-module traceability chain. Backend
remains V1.0.0-alpha.8 at revision `015_p1_8`.

## V1.0.0-beta.5

P2-5 exposes LowCarbonPathRecommendationEngine through a complete recommendation workspace
with target constraints, five-dimensional weighting, candidate control, persisted Top-N
validation, historical lookup and immutable conversion to ScenarioVersion. Backend remains
V1.0.0-alpha.8 at revision `015_p1_8`.

## V1.0.0-beta.4

P2-4 provides the annual/hourly Simulation Workbench, seven unified low-carbon measure forms,
data/provider diagnostics, task execution and hourly energy/carbon/economic result charts.
Temporary changes are frozen into task snapshots and do not mutate immutable ScenarioVersion
records. Backend remains V1.0.0-alpha.8 at revision `015_p1_8`.

## V1.0.0-beta.3

P2-3 exposes P1-2 dynamic accounting in a traceable Carbon Management workspace with Scope,
energy, time and organization analysis, historical run selection and factor provenance. A
minimal read-only discovery/filter layer was added without database migration or accounting
logic changes. Backend remains V1.0.0-alpha.8 at revision `015_p1_8`.

## V1.0.0-beta.2

P2-2 implements the typed, API-backed Data Center across the P1-7 Site hierarchy, devices,
data sources and quality data. It adds reusable trend/composition views, explicit unit and
missing-data handling, recoverable API states and Dashboard deep linking. The backend remains
V1.0.0-alpha.8 with database revision `015_p1_8`.

## V1.0.0-beta.1

P2-1 establishes the Vue 3 frontend foundation and real-API Dashboard. The backend remains
V1.0.0-alpha.8 with database revision `015_p1_8`.

## V1.0.0-alpha.8

P1-8 adds formal DOCX/PDF rendering from immutable report snapshots, artifact checksums,
task lifecycle management and download endpoints. Database revision: `015_p1_8`.

## V1.0.0-alpha.7

P1-7 introduces the localized Site/Building/EnergySystem/MeteringPoint business API layer,
reusing existing ingestion, telemetry, quality and carbon-accounting facts. Database revision:
`014_p1_7`.

## V1.0.0-alpha.6

P1-6 introduced carbon-market scenarios, risk assessment runs and immutable report snapshots.
# V1.0.0-beta.14

- P3-3 多源采集与分级校验能力显性化；后端保持 V1.0.0-alpha.8，数据库保持 `015_p1_8`。
# V1.0.0-alpha.9 / P3-4

- 后端新增 REST 定时采集、MQTT 常驻订阅、自动重连和运行状态 API；前端保持 V1.0.0-beta.14；数据库升级至 `016_p3_4`。
