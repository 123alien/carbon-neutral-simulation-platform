# CBECS 2018 Scope 1 / Scope 2 验证报告

## 链路与边界

官方 raw CSV/codebook → SHA-256 → cleaned → normalized → FastAPI → Carbon Accounting Service → PostgreSQL。没有直接 SQL 写入。独立建立 `Scope1 Validation Site · EIA CBECS 2018`，没有与 BDG2、ACN、Kelmarsh、PVDAQ 或中国目标园区物理混合。

核算期为 2018-01-01 至 2019-01-01，保持年度口径。天然气和柴油归入 Scope 1；购入电力和区域供热按现有核算边界归入 Scope 2。

## 官方因子与单位

使用 US EPA 2020 GHG Emission Factors Hub；CH4/N2O 按该文档采用的 IPCC AR4 GWP（25/298）折算 CO2e：

| 能源 | 因子 | 活动单位转换 | Scope |
|---|---:|---|---|
| 天然气 | 53.1148 kgCO2e/MMBtu | 1 kBtu = 0.001 MMBtu | 1 |
| 柴油/No.2 馏分燃料油 | 74.2138 kgCO2e/MMBtu | 1 kBtu = 0.001 MMBtu | 1 |
| 电力（eGRID2018 US average） | 0.432228623 kgCO2e/kWh | 1 MWh = 1000 kWh；lb 转 kg | 2 |
| 购入热力 | 66.3985 kgCO2e/MMBtu | 1 kBtu = 0.001 MMBtu | 2 |

系统同时自动化验证 `therm → MMBtu`、`GJ → MMBtu`、`gallon` 原单位路径，避免把 therm、gallon 或年度能量误当 kWh/小时功率。

## 正式核算结果

| 能源 | 排放量 tCO2e |
|---|---:|
| Natural Gas（Scope 1） | 301.811360 |
| Fuel Oil / Diesel（Scope 1） | 16.290745 |
| Electricity（Scope 2） | 13,863.282267 |
| District Heat（Scope 2） | 6,670.050694 |
| 合计 | 20,851.435066 |

Scope 1 合计 318.102105 tCO2e；Scope 2 合计 20,533.332961 tCO2e。3 个 Building 均可独立查询，Site 汇总通过组织树聚合子建筑结果，与核算 run 总量一致。每条结果保存原始活动值/单位、标准化值/单位、因子、来源、版本、公式、标准依据和活动来源。

## 页面与报告追溯

碳管理 API 和页面可按 Site、Building、Scope、能源和年度展示，真实 0 与无数据语义保持分离且无 NaN。核算结果具备 ReportEngine 所需的因子与活动来源字段；本轮没有为 CBECS 虚构 ScenarioVersion 或 SimulationTask，因此没有创建混合来源报告快照。

## 真实数据暴露并修复的问题

1. 原核算模型只支持企业常见的 `m³/kg/kWh` 路径，不能接收官方调查的 kBtu/MMBtu、therm、gallon、GJ。已增加按因子单位选择的兼容转换路径，原路径保持不变。
2. Site 碳汇总此前未递归包含挂在子组织节点的 Building 核算结果。已改为按组织树后代聚合，未修改历史事实或核算公式。
