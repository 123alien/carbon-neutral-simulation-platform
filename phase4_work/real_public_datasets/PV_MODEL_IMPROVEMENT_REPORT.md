# PV 模型改进报告

## 审计与改进

- PVDAQ 的 POA 直接进入 POA 模式，没有再次做 GHI 转置。
- 新模型优先使用实测 `module_temperature_c`；缺失时才使用环境温度+NOCT。
- 新增语义明确的 `ac_power_kw()`；旧 `ac_energy_kwh()` 保持兼容并显式乘以 interval hours。
- PVDAQ 15分钟能量严格按 `kW × 0.25h` 积分。
- DC、AC、实测和仿真字段保持分离。
- 首7天校准 PR；后7天独立验证。PR 标记 `CALIBRATED`，不宣称为真实 metadata。

## 受控留出集

验证范围 2010-10-08 至 2010-10-15，共 671 对观测：

| 指标 | legacy POA+NOCT | measured module temperature + calibrated PR |
|---|---:|---:|
| 实测能量 kWh | 3435.600 | 3435.600 |
| 仿真能量 kWh | 4846.084 | 3556.549 |
| MAE kW | 8.499 | 1.603 |
| RMSE kW | 13.501 | 3.231 |
| nRMSE | 11.095% | 2.655% |
| Energy Error | +41.055% | +3.520% |
| Correlation | 0.9925 | 0.9936 |

参数来源：装机容量、组件数量/功率、方位角、逆变器容量和组件温度为 `REAL_METADATA`；PR 为 `CALIBRATED`；逆变器效率0.96和温度系数-0.004/°C为 `MODEL_DEFAULT`。没有对真实功率做缩放或删除观测。
