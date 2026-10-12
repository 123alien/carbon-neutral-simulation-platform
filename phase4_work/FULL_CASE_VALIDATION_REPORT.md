# P3-1 完整案例数据与全链路验证报告

> 验证日期：2026-08-25。案例数据全部为 **DEVELOPMENT / DEMO / VALIDATION** 合成数据，不代表任何真实企业、园区或交易所行情。

## 1. 验证结论

`carbon_neutral_dev.db` 中已经形成一条可追溯的完整链路：数据接入 → 数据质量 → Scope 1/2 核算 → 四场景小时仿真 → 三类 Top-N 推荐 → 批量比较 → 碳市场 → 六类风险 → 不可变报告快照 → DOCX/PDF → Dashboard/大屏/3D。前端 12 个核心路由均以真实开发库数据加载成功，无白屏、无浏览器控制台错误。

版本保持 Frontend `V1.0.0-beta.13`、Backend `V1.0.0-alpha.8`、Alembic `015_p1_8`。本轮仅修复负荷导入的未来时间戳校验缺陷，没有数据库迁移或算法变更。

## 2. 案例基础信息

| 项目 | 值 |
|---|---|
| Site | 碳中和示范园区（`DEMO-PARK-001`，PARK） |
| 时区 | Asia/Shanghai |
| 面积 / 人口 | 35,000 m² / 1,450 人 |
| 时间范围 | 2024-01-01 00:00 至 2024-12-31 23:00 |
| 小时数 | 8,784（闰年） |

### Building

| Code | 名称 | 类型 | 面积 | 人口 | 局部坐标 (x,y,z) |
|---|---|---|---:|---:|---|
| B01 | 综合办公楼 | OFFICE | 10,000 m² | 650 | (-40,0,-20) |
| B02 | 科研实验楼 | LAB | 8,000 m² | 420 | (20,0,-25) |
| B03 | 数据中心 | DATA_CENTER | 5,000 m² | 80 | (55,0,20) |
| B04 | 综合服务楼 | SERVICE | 7,000 m² | 300 | (-25,0,35) |
| B05 | 停车及充电区域 | PARKING | 5,000 m² | 0 | (45,0,55) |

### EnergySystem / Device / MeteringPoint

- 7 个能源系统：园区电力、光伏、风电、储能、HVAC、照明、EV 充电。
- 13 台/组设备：总电表 1、建筑电表 5、105 kWp 光伏阵列/逆变器、小型风机组 2×20 kW、100 kW/200 kWh 储能、HVAC 2、照明聚合设备 1、20×7 kW 充电桩聚合设备 1。
- 10 个计量点：园区总用电、5 个建筑用电、PV 发电、WIND 发电、STORAGE 充放电、EV 充电；均绑定 Device、EnergySystem、能源类型、指标和单位。

### DataSource

| Code | 类型 | 用途 |
|---|---|---|
| DEV_LOAD_FILE | FILE | 总负荷及分项设备指标 |
| DEV_WEATHER_FILE | FILE | 气象与辐照 |
| DEV_PRICE_FILE | FILE | 峰平谷电价 |
| DEV_GRID_EF_FILE | FILE | 动态电网排放因子 |
| DEV_REST_SAMPLE | REST_API | 开发配置占位，不冒充在线数据 |
| DEV_MQTT_SAMPLE | MQTT | 开发配置占位，不冒充在线 IoT |

## 3. 数据统计与接入验证

- 小时负荷：8,784 行，年用电 4.7791 GWh，峰值 873.24 kW；含工作日、昼夜、夏冬 HVAC、数据中心基载和 EV 日内规律。
- 分项设备指标：61,488 行（7 个主要设备 × 8,784 小时），用于建筑趋势、设备遥测和 DataSource 质量视图。
- 气象：8,784 行，含温度、湿度、GHI/DNI/DHI、风速、云量；夜间辐照为 0，湿度及辐照范围通过校验。
- 电价：谷 0.40、平 0.72、峰 1.10 元/kWh，上网电价 0.38 元/kWh。
- 排放因子：动态小时因子 `DEMO-2024-HOURLY`，地区 `DEMO_REGION`；固定 fallback 为 0.56 kgCO2/kWh；天然气因子 2.162 kgCO2/m³。
- 绿电合同：2024 年，15% 购电比例，0 kgCO2/kWh，溢价 0.06 元/kWh。
- 正常时序均通过既有 Preview → Confirm 接口导入；Preview 阶段未写库。重复执行装载脚本后对象和时序数量不增长。

### 数据质量

| 数据 | 观测/期望 | 缺失 | 重复/隔离 | 完整率 | 结果 |
|---|---:|---:|---:|---:|---|
| 总负荷 | 8784/8784 | 0 | 0 | 100% | COMPLETE |
| 气象 | 8784/8784 | 0 | 0 | 100% | COMPLETE |
| 设备指标 DataSource | 61488/61488 | — | 0 | 100% | 通过 |

异常样本只执行 Preview、从未 Confirm：重复时间戳、缺失间隔、非法数值/单位样本、越界湿度、未来时间戳均为 `can_confirm=false`，并返回具体错误行。

## 4. 碳核算

核算运行 `id=1`，包含 12 个月电力和 12 个月天然气活动数据，共 24 条结果：

| Scope / 能源 | 排放量 |
|---|---:|
| Scope 1 / 天然气 | 351.6715 tCO2e |
| Scope 2 / 电力 | 2,862.5265 tCO2e |
| 合计 | 3,214.1980 tCO2e |

活动数据、标准化值、因子来源/版本、公式和标准依据可在 `/carbon` 追溯，并支持日/月/年与能源维度展示。

## 5. 四场景小时仿真与比较

批量任务 `id=1` 状态 `SUCCESS`，4 个场景分别绑定独立 ScenarioVersion 和 SimulationTask，共保存 35,104 条小时结果。13 项统一比较指标及 baseline 差值/变化率均由后端返回。

| 场景 | 总碳排 t | 减排 t / 率 | 购电 MWh | 可再生发电 MWh | 总电费 万元 | 投资 万元 | 回收期 年 | 最大守恒误差 kWh |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BASELINE | 2,204.606 | 0 / 0% | 4,775.874 | 0 | 359.627 | 0 | — | 0 |
| ECONOMIC | 2,059.984 | 144.622 / 6.56% | 4,462.577 | 0 | 336.035 | 30 | 1.272 | 0 |
| REDUCTION | 1,991.148 | 213.458 / 9.682% | 4,571.347 | 204.527 | 344.094 | 111 | 7.146 | 1.14e-13 |
| BALANCED | 2,069.511 | 135.094 / 6.128% | 4,465.472 | 143.268 | 334.602 | 195.5 | 7.812 | 1.14e-13 |

完整案例的措施配置覆盖 PV、WIND、STORAGE、HVAC、LIGHTING、EV_CHARGER、GREEN_POWER 七类；能源守恒误差在浮点精度范围内。

## 6. 推荐、碳市场、风险与报告

- 推荐运行 `id=1`：ECONOMIC、REDUCTION、BALANCED 各 Top-3，共 9 条，页面真实展示五维评分、投资、减排、回收期及仿真验证。
- 碳成本评估 `id=1`：原始/净排放 2,069.511 t，配额 2,200 t，盈余 130.489 t；绿证成本 3,250 元，配额盈余价值 10,700.08 元，综合碳成本 -7,450.08 元；`physical_energy_balance_changed=false`。
- 风险评估 `id=1`：整体 MEDIUM，六类风险结果和建议完整保存并展示。
- 报告任务 `id=1`：不可变快照 `id=1`；DOCX 198,163 bytes，PDF 252,837 bytes，均保存 SHA-256、生成时间和下载记录。两种格式来自同一快照。

## 7. 前端验收

真实浏览器逐页检查 `/dashboard`、`/data`、`/carbon`、`/simulation`、`/recommendations`、`/scenarios`、`/carbon-market`、`/risks`、`/reports`、`/system`、`/screen`、`/3d`：全部 HTTP 200，无致命加载提示、无 console error。

- Dashboard：园区、建筑、设备、数据源、碳排、能源及最近仿真均有真实数据。
- 数据接入工作台：六步业务流程可见，园区/建筑/系统/设备/计量点/数据源及质量数据已加载。
- 综合大屏：碳排、能源、措施、推荐、空间、场景、市场、风险和趋势模块有数据。
- 3D：WebGL canvas 成功创建，Site、5 栋建筑和关联设备名称可见；空间坐标来自数据库。
- 报告中心：快照章节、DOCX/PDF、文件大小、SHA-256 和下载入口可见。

截图和机器可读结果位于 `qa_report/full_case/` 与 `demo_data/frontend_validation_result.json`。

## 8. 缺陷与处理记录

| 编号 | 页面/功能 | 输入 | 预期 | 实际 | 结论 | 修复情况 |
|---|---|---|---|---|---|---|
| P3-001 | 建筑趋势/设备遥测 | 仅 LoadTimeseries 总负荷 | 分建筑和设备应有小时曲线 | LoadTimeseries 不会自动生成 DeviceMetric | 数据接入语义缺口 | 新增确定性 `device_metrics_2024.csv`，经现有 FILE Adapter 入库 61,488 行；未绕过校验链 |
| P3-002 | 负荷异常 Preview | 2099 年时间戳 | 禁止确认并报告错误行 | 原实现 `can_confirm=true` | 后端校验缺陷 | 已增加未来时间戳校验和自动化测试；现在 `can_confirm=false` |
| P3-003 | `/data` 设备统计 | 13 个设备，其中 10 个有计量点 | 页面应遵循接口口径 | Site 数据页显示 10 台关联计量设备 | 通过（口径说明） | 数据库保留全部 13 台；localized API 的设备数按计量关联口径统计，不伪造数量 |
| P3-004 | 前端生产构建 | ECharts/Three.js | 构建成功 | 成功，但部分 chunk >500 kB | 非阻塞性能提醒 | 尚未做 manualChunks；列为后续性能优化项 |

尚未解决的阻塞缺陷：无。已知非阻塞项：前端包体积提示，以及旧代码中的 `datetime.utcnow()`/FastAPI lifespan 弃用警告。

## 9. Development 数据库最终数量

| 表/对象 | 数量 |
|---|---:|
| enterprise / site / building | 1 / 1 / 5 |
| energy_system / device / metering_point / data_source | 7 / 13 / 10 / 6 |
| load_timeseries / weather_timeseries | 8,784 / 8,784 |
| electricity_price_timeseries / grid_emission_factor_timeseries | 8,784 / 8,784 |
| device_metric | 61,488 |
| carbon_accounting_run / result | 1 / 24 |
| scenario / scenario_version | 4 / 4 |
| simulation_batch / item / task / hour_result | 1 / 4 / 4 / 35,104 |
| recommendation_run / recommendation | 1 / 9 |
| carbon_market_scenario / timeseries / assessment | 1 / 12 / 1 |
| risk_run / risk_result | 1 / 6 |
| report_task / snapshot / file | 1 / 1 / 2 |

## 10. 自动化与可重复性

- `scripts/generate_demo_dataset.py`：16 个生成文件重复生成 SHA-256 完全一致。
- `scripts/load_demo_case.py`：二次执行复用已有对象和 8,784/61,488 行数据，无重复写入。
- `scripts/run_demo_full_chain.py`：二次执行复用核算、场景、批次、推荐、风险和报告，ID 不变。
- `python -m pytest -q`：**44 passed**。
- `npm run e2e`：**9 passed**。
- `npm run build`：`vue-tsc -b` 与 `vite build` 均通过。

