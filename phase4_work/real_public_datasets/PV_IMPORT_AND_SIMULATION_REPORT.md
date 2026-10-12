# PV 导入与模型验证报告

## 实测字段和参数

System 35 提供 POA 辐照、环境/组件温度、DC 功率和 AC 功率。本次只将 `ac_power_kw` 与模型 AC 输出比较；DC 未冒充 AC，15 分钟功率通过 `kW × 0.25 h` 积分为 kWh。

真实 metadata：121.68 kWp、Sharp 240 W × 507、Satcon 135 kW 逆变器、方位角 270°。倾角缺失；POA 模式直接使用实测 POA，因此倾角 fallback 不参与辐照转换。

`MODEL_PARAMETER_FALLBACK`：performance ratio 0.85、inverter efficiency 1.0、NOCT 45°C、温度系数 -0.004/°C、degradation factor 1.0。inverter efficiency 取 1 是为了不与聚合 performance ratio 重复计算效率。

## 实测与仿真

| 配对点 | 实测 AC 发电量 | 仿真 AC 发电量 | MAE | RMSE | nRMSE（DC 容量） | Energy Error | Correlation |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,343 | 6,403.55 kWh | 8,865.35 kWh | 7.688 kW | 13.238 kW | 10.879% | +38.444% | 0.9785 |

## 模型审计结论

- GHI/POA：本次明确使用 POA 模式和实测 POA，没有把 GHI 当 POA。
- DC/AC：实测 DC 与 AC 分列；比较基准只用实测 AC。
- 温度：当前模型使用环境温度经 NOCT 估算电池温度，尚不能直接采用已观测的组件温度。
- 效率：未重复套用 performance ratio 与 inverter efficiency；后者在本次设为 1。
- degradation：只应用一次且 fallback 为 1。
- kW/kWh：模型方法名 `ac_energy_kwh` 在小时引擎中代表一小时能量，但返回值数值本质为时段平均功率；本次 15 分钟验证明确按功率比较并乘 0.25 积分。

真实数据表明当前模型保持很高的趋势相关性，但能量高估 38.44%。主要限制是站点 PR、NOCT、温度系数缺失及模型未直接利用实测组件温度。没有通过修改观测或任意调参消除偏差；本轮不作缺乏真实参数依据的模型校准，能力标记为 `VERIFIED_WITH_LIMITATION`。
