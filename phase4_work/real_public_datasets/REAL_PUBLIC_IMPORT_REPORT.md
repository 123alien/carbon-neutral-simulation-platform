# 第一轮公开真实数据导入报告

## 导入对象

- Validation Site：`BDG2 Rat Validation Site`，Site ID 1，时区 `US/Eastern`。
- Building：`Rat_education_Theo`、`Rat_education_Kathryn`、`Rat_office_Colby`、`Rat_office_Avis`、`Rat_public_Kimber`。
- 正式聚合区间：2016-03-13 03:00 至 2016-11-05 23:00（本地时间），连续 5709 小时。
- 全年原始观测：每栋 8782/8784，完整率 99.9772%；5 栋共 43,910 条，无负值。缺失值未生成、未补零。

## 转换与导入

- 原始宽表转为长表；保留原始建筑 ID。
- BDG2 `electricity` 为小时 `kWh_sum`；按一小时区间换算平均功率 kW，仅用于小时负荷接口。
- 5 栋聚合仅取共同连续完整区间，没有插值、年份平移或异常替换。
- FILE Adapter：extracted 43,910，L1/L2/L3 后 inserted 43,910，quarantined 0，warnings 0。
- Load Preview：5709 valid、0 invalid、0 duplicate、0 missing；Confirm 5709。
- Weather Preview：NASA POWER 5709 valid、0 invalid、0 missing；Confirm 5709。
- 中国 2024 官方因子：Preview 1 valid，Confirm 1；与 BDG2 美国 2016 核算隔离。

## PostgreSQL 变化

| 表/对象 | 导入前 | 导入后 |
|---|---:|---:|
| site | 0 | 1 |
| building | 0 | 5 |
| energy_system | 0 | 1 |
| device | 0 | 5 |
| metering_point | 0 | 5 |
| device_metric | 0 | 43,910 |
| load_timeseries | 0 | 5,709 |
| weather_timeseries | 0 | 5,709 |
| carbon_accounting_result | 0 | 28,545 |
| scenario_version | 0 | 1 |
| simulation_task | 0 | 1 |

## 核算、仿真与桥接

- Scope 2 核算：28,545 条活动结果，11,567.905015 tCO2；使用 US EPA eGRID2016 全国 CO2 输出率 998.4 lb/MWh，换算 0.452866622208 kgCO2/kWh，年度 fallback，未伪造动态因子。
- DeviceMetric 聚合：25,543,735.060000148 kWh；LoadTimeseries：25,543,735.059999947 kWh；浮点差约 0.000000201 kWh。
- 小时基准仿真：5709 小时，基准负荷/购电 25,543,735.06 kWh，碳排 11,567.905015 tCO2，最大能源守恒误差 0。
- 电费结果不作为真实验证结论：湖北政策只有时段倍率且地域不匹配，仿真使用的固定 fallback 不是 BDG2 实际结算价。

## 报告

Report 2 已从冻结快照生成 DOCX/PDF。快照新增 `data_provenance`，明确数据集、公开真实分类、来源 URL、时间范围及局限。数据库 revision 保持 `016_p3_4`。

最终文件：DOCX 151,973 bytes，SHA-256 `7b538275842a149f017cd4d374fb7f525a233fa1de2007b308a5d187e30c7834`；PDF 143,107 bytes，SHA-256 `0f6e0ab3573da6ca4bd29acf996142d50384347cd762136119e295d092b80569`。DOCX 结构校验确认来源章节、dataset ID 与 9 张图表均存在。由于本机 LibreOffice 的 `bootstrap.ini` 损坏，独立 DOCX→PNG 视觉渲染门禁未能执行；平台自身 PDF Renderer 已正常生成有效 `%PDF` 文件。

## 回归结果

- Backend：47 passed，1 skipped。
- Frontend Playwright：12 passed（含 2 项 P3-5 真实库专项）。
- `vue-tsc -b` + `vite build`：通过；仅保留既有大 chunk 警告。

机器可读明细见 `manifests/first_round_api_results.json`。
