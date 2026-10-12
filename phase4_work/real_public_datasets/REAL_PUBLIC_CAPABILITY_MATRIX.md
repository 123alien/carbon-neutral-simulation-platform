# 公开真实数据能力覆盖矩阵（第一轮）

P3-5.2.1：通用 REST `TIME_WINDOW` 与 `LINK_NEXT` 已由隔离协议服务验证；ACN `_links.next.href` 仅完成 fixture 兼容验证。因无合法 Token，ACN 官方公网 REST 仍为 **BLOCKED_BY_ACCESS**，不能标记为官方集成成功。

| 平台能力 | 数据来源 | Validation Site | 接入 | 实测/官方 | 已导入 | 已验证 | 备注 |
|---|---|---|---|---|---|---|---|
| Site / Building / EnergySystem / Device / MeteringPoint | BDG2 | Building Energy Validation Site | API | 公开实测研究数据 | 是 | 是 | 1/5/1/5/5 |
| FILE / L1-L2-L3 | BDG2 electricity | 同上 | FILE Adapter | 公开实测 | 是 | 是 | 43,910，拒绝 0 |
| Hourly Load | BDG2 electricity | 同上 | Preview/Confirm | 公开实测 | 是 | 是 | 5709 连续小时 |
| Weather | NASA POWER | 同上坐标 | Preview/Confirm | 官方再分析/遥感数据 | 是 | 是 | 5709 点 |
| Grid EF / Scope 2 | EPA eGRID2016 | 同上 | Provider fallback | 官方年度数据 | 是 | 是 | 2016 年同年口径 |
| China Grid EF | 中国生态环境部 2024 | China Market Context | Preview/Confirm | 官方 | 是 | 是 | 与 BDG2 隔离 |
| Electricity Price | 湖北分时政策 | China Market Context | 文件/规则上下文 | 官方 | 否 | 规则已核验 | 仅倍率，无企业基准价；未应用于 BDG2 |
| Carbon Accounting | BDG2 + eGRID | Building Energy Validation Site | Service/API | 真实输入、模型核算 | 是 | 是 | 11,567.905015 tCO2 |
| Simulation | BDG2 + NASA + eGRID | 同上 | Hourly engine | 真实输入、模型输出 | 是 | 是 | 守恒误差 0；经济性未验证 |
| Scenario | BDG2 baseline | 同上 | API | 模型对象 | 是 | 是 | 不可变版本 1 |
| Risk | baseline task | 同上 | API | FUNCTION_VERIFIED_ONLY | 是 | 是 | 无真实市场价格波动输入，不作真实风险结论 |
| Report | 冻结快照 | 同上 | DOCX/PDF | 真实输入、模型报告 | 是 | 是 | 含来源与局限 |
| Dashboard / Carbon / Simulation / Report UI | 上述数据 | 同上 | Frontend API | 真实输入 | 是 | 是 | Playwright 真实库专项通过，无 NaN |
| Recommendation / Scenario Comparison | BDG2 baseline | 同上 | Engine/API | FUNCTION_VERIFIED_ONLY | 否 | 待下一轮 | 推荐可提出措施，但不表示已有设备 |
| EV_CHARGER | ACN-Data Static | ACN Caltech EV Charging Validation Site | FILE official-author export | 公开实测 | 是 | VERIFIED | 3 stations / 122 sessions；116 session totals 入库 |
| DeviceMetric / Field Mapping / L1-L2-L3 | ACN-Data Static | 同上 | FILE Adapter | 公开实测 | 是 | VERIFIED | 116/116；session gap NOT_APPLICABLE |
| REST_API / REST Scheduler / Runtime Monitoring | ACN official API | 同上 | REST_API | 公开实测 API | 否 | BLOCKED_BY_ACCESS | Token required；真实无凭证请求 401；未伪造成功 |
| REST pagination / incremental window | 隔离协议服务；ACN schema fixture | 同上 | TIME_WINDOW + LINK_NEXT | 协议验证 | 否 | VERIFIED（通用能力） | ACN 公网仍 BLOCKED_BY_ACCESS，不等同官方集成成功 |
| MQTT | 待真实公开回放 | 独立 Site | MQTT | 待获取 | 否 | P3-4 管道已验证 | P3-5 数据验证待后续 |
| PV / Irradiance / Temperature / Actual PV Generation | NREL PVDAQ System 35 | PV Validation Site · NREL PVDAQ 35 | FILE Adapter Preview/Confirm | 公开实测 | 是 | VERIFIED | 1 system、14 天、6,717 指标；POA、环境/组件温度、DC/AC 功率严格区分 |
| PV Simulation / Observed vs Simulated | PVDAQ 35 + SolarIrradianceModel | 同上 | POA model validation | 实测输入、模型输出 | 是 | VERIFIED_WITH_LIMITATION | 实测 6,403.55 kWh；模型 +38.44%；PR/NOCT/温度系数等为 fallback |
| HVAC / DeviceMetric / Data Quality | Pecan Street 官方公开 Kaggle 样本 | Distributed Energy Validation Site · Pecan Street | FILE Adapter Preview/Confirm | 公开实测 | 是 | VERIFIED | 3户、1分钟、3天；冷凝机/风机功率及明确派生合计；38,889 条 |
| HVAC Simulation Input | Pecan Street HVAC 实测功率 | 同上 | Hourly engine isolated component validation | 实测输入、规则输出 | 是 | VERIFIED_WITH_LIMITATION | 实测输入 487.501 kWh；10% saving_rate 为 MODEL_PARAMETER_FALLBACK；不代表实测节能率 |
| Lighting | Pecan Street Dataport 扩展样本 | 同上 | 需注册许可 | 官方说明可提供 | 否 | BLOCKED_BY_ACCESS | 公开3天 Kaggle样本无照明回路，不用二手数据冒充 |
| Storage charge/discharge/SOC | Pecan Street Dataport | 同上 | 需账户/许可 | 官方说明存在储能数据 | 否 | BLOCKED_BY_ACCESS | 无合法数据，未创建 Storage Device、未推导 SOC |
| WIND / Wind SCADA / Wind Speed / Actual Power | Kelmarsh Wind Farm | Wind Validation Site · Kelmarsh UK | FILE Adapter Preview/Confirm | 公开实测 | 是 | VERIFIED | 3 台、14 天、30,240 指标；状态保留；不与中国园区混合 |
| Wind Simulation / Observed vs Simulated | Kelmarsh + 当前 WindGenerationModel | 同上 | 模型验证 | 实测输入、模型输出 | 是 | VERIFIED_WITH_LIMITATION | 真实额定功率；切入/额定/切出风速为 MODEL_PARAMETER_FALLBACK；能量误差 -47.01%，模型明显低估 |
| Scope 1 / Scope 2 / multi-energy accounting | EIA CBECS 2018 + EPA GHG Hub/eGRID2018 | Scope1 Validation Site · EIA CBECS 2018 | Accounting Service/API | 官方年度调查与官方因子 | 是 | VERIFIED | 3栋、12条年度活动；天然气/柴油 Scope 1，电力/区域供热 Scope 2；不伪装小时 SCADA |
| CBECS Building/Site aggregation and traceability | 同上 | 同上 | Carbon Management API/UI | 官方输入、模型核算 | 是 | VERIFIED | 原始/标准化单位、因子、来源、版本、公式、标准依据可追溯；无 NaN |
| National Carbon Market price/volume/amount | 生态环境部 2024–2025 年度公告 | China Market Validation Context | Statistics API | 官方年度汇总 | 是 | VERIFIED | 2条年度观测；不同价格口径已标注，不伪造日线或企业交易 |
| CCER price/volume/amount | 生态环境部 2025 年度公告 | China Market Validation Context | Statistics API | 官方年度汇总 | 是 | VERIFIED_WITH_LIMITATION | 1条观测，不伪造趋势；无真实企业 CCER 持仓 |
| Green Certificate issued/traded/price | 国家能源局 2024–2025 发展报告 | China Market Validation Context | Statistics API | 官方年度汇总 | 是 | VERIFIED | 2条年度观测；非绿电合同、非企业持仓 |
| CarbonCost / Price volatility / Report | 上述官方市场价格 + 功能参数 | China Market Validation Context | Engine/ReportEngine | 官方价格；企业参数非真实 | 是 | FUNCTION_VERIFIED_ONLY | 配额、抵消量、绿证数量均标记 FUNCTION_PARAMETER_ONLY；未声称企业市场结论 |
| Big Screen | BDG2 | Building Energy Validation Site | Frontend API | 真实输入 | 是 | 是 | 页面可加载且无 NaN |
| 3D | BDG2 | Building Energy Validation Site | Frontend API | 坐标仅站点级 | 是 | 是 | 页面可加载；建筑布局不得称为真实坐标 |
