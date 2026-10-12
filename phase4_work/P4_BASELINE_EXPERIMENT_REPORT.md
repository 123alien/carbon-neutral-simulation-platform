# P4-1 真实基准场景实验报告

## 基准边界

- 唯一物理站点：BDG2 Rat Validation Site（Site 1，`BDG2-RAT`）。
- 建筑：5 栋，未混入 ACN、Kelmarsh、PVDAQ、Pecan Street 或 CBECS 数据。
- UTC 时间范围：`2016-03-13T07:00:00Z`（含）至 `2016-11-06T04:00:00Z`（不含），共 5,709 个连续小时，完整率 100%。
- 数据来源：BDG2 V1 真实公开数据；气象为同坐标、同时间范围 NASA POWER 真实公开数据。

## 不可变基准

- Scenario：#1。
- ScenarioVersion：#3 / V3，类型 `BASELINE`，状态 `LOCKED`。
- 低碳增量措施全部为 0；其语义是“不新增措施”，不是删除站点已有设备。
- P4-2 及后续实验必须使用 `compare_to = 3`。
- 冻结快照见 `P4_BASELINE_EXPERIMENT_SNAPSHOT.json`，其中包含数据来源、时间范围、因子、模型版本、参数来源、目标结构和 SHA-256。

## 基准结果

| 指标 | 结果 | 验证状态 |
|---|---:|---|
| 总能耗 | 25,543,735.06 kWh | REAL_PUBLIC |
| 电网购电 | 25,543,735.06 kWh | REAL_PUBLIC + simulation verified |
| 可再生能源发电 | 0 kWh | no incremental measure |
| Scope 1 | NOT_VERIFIED | BDG2 本基准没有可靠 Scope 1 活动数据 |
| Scope 2 | 11,567.905015 tCO2e | eGRID2016 official factor |
| 已验证边界总排放 | 11,567.905015 tCO2e | Scope 2 only |
| 峰值负荷 | 7,290.88 kW | REAL_PUBLIC |
| 电费、碳成本、总成本 | NOT_VERIFIED | 缺少站点匹配的真实结算价格和碳成本 |
| 可再生能源占比 | 0 | baseline incremental measure boundary |
| 最大能源守恒误差 | 0 kWh | verified by hourly results |

引擎仍保留 0.57 CNY/kWh 购电价和 0.42 CNY/kWh 上网价用于功能计算，但二者均标记为 `FUNCTION_PARAMETER_ONLY`，不得作为真实经济性结论。

## 口径桥接与重复性

DeviceMetric 保存 5 个建筑逐小时事实，LoadTimeseries 保存同 5 栋建筑的站点逐小时合计。因此两表行数不同但活动量完全一致：DeviceMetric、LoadTimeseries 和 Carbon Accounting Input 均为 25,543,735.06 kWh，差值 0 kWh。Accounting Scope 2 与 Simulation Baseline 均为 11,567.905015 tCO2e，仅有浮点尾差。

ScenarioVersion #3 连续执行 SimulationTask #2 与 #3，两次均为 5,709 小时，总能耗、购电量、排放和最大守恒误差完全一致。

ReportTask #4 已绑定 ScenarioVersion #3、SimulationTask #2 和 CarbonAccountingRun #3；其 `report_snapshot` 已冻结上述版本和任务输入，后续源状态变化不会替换本次基准报告数据。

## 限制

- BDG2 本实验窗口只验证站点用电及 Scope 2，Scope 1 不补零。
- 当前基准没有站点匹配的真实电价、碳价或企业配额，成本均不形成真实结论。
- 公开研究数据不代表中国目标企业的物理或结算事实。
