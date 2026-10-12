# P4-2 低碳措施候选库与参数审计

## 审计边界

本目录只服务于锁定基准 `ScenarioVersion #3`（BDG2-RAT，5 栋建筑，5,709 小时）。规模上限来自基准峰值 7,290.88 kW 和能耗 25,543,735.06 kWh；这只是实验搜索边界，不等于场地可建设规模。投资、运维、电价和绿电溢价没有 BDG2 真实合同或报价，统一为 `FUNCTION_PARAMETER_ONLY`。

`LOW / MEDIUM / HIGH` 已写入 `P4_MEASURE_PARAMETER_CATALOG.json`。默认实验级别为 `MEDIUM`，推荐输入和结果会保存最终参数；不得仅保存级别名称。

## 实际模型与参数结论

### PV

小时模型使用 capacity、GHI/POA、组件或环境温度、PR、逆变器效率、温度系数和 degradation。PVDAQ 校准 PR `0.799242` 是 `CALIBRATED`，不是设备铭牌参数。BDG2 有真实公开辐照，但没有屋顶可用面积、倾角、方位角和设备 metadata；因此倾角/方位角为 `MODEL_PARAMETER_FALLBACK`。当前 AC 公式分别乘 PR 与 inverter efficiency，目录将校准 PR 与 inverter efficiency=1 配对，避免把既有系统损失重复计算。候选可有限进入推荐，投资结论不可验证。

### WIND

实际参数为 rated power、curve mode、cut-in/rated/cut-out、power curve、参考空气密度及运行状态。支持 `SIMPLE_CURVE`、`MANUFACTURER_CURVE`、`CALIBRATED_CURVE`。BDG2 没有风机 metadata 或厂商曲线，Kelmarsh 校准曲线不能跨站点冒充，因此实验仅允许 `SIMPLE_CURVE` fallback；风电可作有限敏感性候选，不能给出真实项目可行性结论。

### STORAGE

模型逐时维护 SOC，执行功率、效率和 SOC 边界，并用 `elif` 保证同小时充放电互斥。目录验证 `soc_min <= soc_initial <= soc_max`。`cycle_limit` 当前没有进入老化/调度逻辑，明确记为模型限制。负荷约束真实，效率、SOC、寿命和成本为默认或功能参数。可直接进入技术推荐，但经济性只能作为功能比较。

### HVAC

实际模型为 `facility_load × load_share × saving_rate`，不是逐时热工或设备物理模型，已显式标记 `MODEL_LIMITATION`。Pecan Street 只证明模型能接收真实 HVAC 分项数据，不能把另一站点数据作为 BDG2 affected load。可有限用于敏感性推荐。

### LIGHTING

模型支持静态 load share/saving rate 或灯具数量与功率差。真实照明分项仍为 `BLOCKED_BY_ACCESS`，BDG2 也没有灯具台账，因此默认禁用。取得真实分项或明确实验假设后才能启用。

### EV_CHARGER

当前小时模型实际生成新增充电负荷，参数是枪数、单枪功率、利用率、日能量、充电窗口或 24 小时曲线；它不是“对既有观测 EV 负荷进行 shift”的优化器。ACN 数据属于另一物理站点，BDG2 没有真实 EV profile 和人口，因此 `charging_shift_ratio / peak_reduction` 不能直接驱动当前模型，候选标记 `BLOCKED_BY_ACCESS` 并默认禁用。

### GREEN_POWER

模型只在电网购电之后分配绿电属性和溢价，不改变物理能源守恒。BDG2 无真实合同，采购比例、溢价、绿电因子和期间均为 `FUNCTION_PARAMETER_ONLY` 或 fallback。允许有限情景分析，不得称为真实合同结果。

## 组合与重复计算审计

- PV + Storage：允许；仅可用可再生能源盈余充电，储能不产生能源。
- PV + Green Power：允许；先做物理 PV 平衡，再对剩余电网购电分配绿电属性，Scope 2 不重复减排。
- HVAC + Lighting：允许；总节能已封顶于 facility load，但两者 affected load 重叠时仍需人工复核。
- Storage charge + discharge：同小时禁止，模型已有运行时保护。
- Green Power + Grid EF reduction：同一电量属性不得重复声明。
- PV 的 PR、inverter efficiency、degradation：分别只应用一次；校准 PR 已吸收的系统损失不得再次乘入。

## 推荐准入矩阵

| Measure | 主要参数来源 | 真实验证 | P4 推荐 | 限制 |
|---|---|---|---|---|
| PV | 辐照 REAL_METADATA；PR CALIBRATED；几何 fallback；成本 FUNCTION | 模型已用 PVDAQ 留出集验证 | 有限使用 | 面积与设备参数未验证 |
| WIND | 风速 REAL_METADATA；曲线/阈值 fallback；成本 FUNCTION | 模型已用 Kelmarsh 留出集验证 | 有限使用 | 无 BDG2 厂商曲线/风机 metadata |
| STORAGE | 负荷 REAL_METADATA；效率/SOC MODEL_DEFAULT；成本 FUNCTION | 边界、互斥、守恒已验证 | 可直接进入技术推荐 | cycle limit 未建模，经济性非真实 |
| HVAC | 模型默认；Pecan 仅跨站验证；BDG2 affected load fallback | 静态节能逻辑已验证 | 有限使用 | `MODEL_LIMITATION` |
| LIGHTING | MODEL_DEFAULT / fallback | 真实数据未取得 | 暂不进入 | `BLOCKED_BY_ACCESS` |
| EV_CHARGER | ACN 跨站真实验证；BDG2 profile 缺失 | 接入/新增负荷模型已验证 | 暂不进入 | `BLOCKED_BY_ACCESS`；尚非 shift 优化器 |
| GREEN_POWER | 合同与价格 FUNCTION；因子 fallback | 计算逻辑已验证 | 有限使用 | 无真实 BDG2 合同，不改变物理平衡 |

## 代码级问题与处置

1. 旧候选库成本常数没有来源标签：保留功能计算，统一标记 `FUNCTION_PARAMETER_ONLY`。
2. 推荐页以前默认启用全部七类措施：BDG2 P4 目录现在自动禁用 LIGHTING 和 EV_CHARGER。
3. 厂商风机模式以前可能被名称误解：参数校验现在要求 MANUFACTURER/CALIBRATED 至少包含两个导入曲线点。
4. 推荐参数以前只校验 JSON 结构：后端现增加数值边界、SOC 顺序和风速阈值校验。
5. P4 推荐候选现在携带 `parameter_sources` 与 `recommendation_status`，便于后续场景与报告固化来源。
