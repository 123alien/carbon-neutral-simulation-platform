# Wind SCADA 导入与仿真验证报告

## 导入追溯

Kelmarsh 公开 SCADA 以正式 FILE Adapter 完成预览后确认导入，目标为独立 `Wind Validation Site · Kelmarsh UK`。站点元数据明确记录英国来源及 `not_target_china_site=true`，未冒充中国目标园区。标准文件为 `devices.csv`、`metering_points.csv`、`wind_metrics.csv`；实测风速、实测有功功率和仿真功率语义严格分离。

## 参数分类

- 真实 metadata：Senvion MM92；每台额定功率 2,050 kW；轮毂高度 78.5/78.5/68.5 m；叶轮直径 92 m。
- `MODEL_PARAMETER_FALLBACK`：切入 3 m/s、额定 12 m/s、切出 25 m/s。数据集未提供这些值，因此结果仅称为 **model validation under fallback parameters**。

## 实测与仿真

| 范围 | 实测发电量 kWh | 仿真发电量 kWh | MAE kW | RMSE kW | nRMSE（额定功率） | Energy error | Correlation |
|---|---:|---:|---:|---:|---:|---:|---:|
| 全部 6,048 点 | 873,281.048 | 462,760.641 | 408.339 | 507.777 | 24.770% | -47.009% | 0.9061 |
| 排除活动 `Status=Stop` 区间（2,016 点） | 294,086.473 | 162,181.697 | 394.035 | 484.173 | 23.618% | -44.852% | 0.9150 |

## 暴露的问题与处置

1. 当前通用三段式风机曲线明显低估 MM92 实测发电量约 45%–47%。没有调数据或改阈值追求好看结果；应在后续引入厂商功率曲线、空气密度与可用率/限功率状态建模后再校准。
2. 真实 10 分钟 SCADA 暴露了页面小时聚合把瞬时风速求和的问题。已作最小修正：`kWh/m³/kg/t` 等累计量求和，风速和有功功率等瞬时量取平均，并增加回归测试。
3. Published 状态为事件区间，`Stop` 与仍有功率观测可能并存。原状态完整保留，报告明确筛选条件，不删除冲突点。

结论：数据接入、质量校验和现有模型的真实输入验证成立；模型精度只标记为 `VERIFIED_WITH_LIMITATION`，不应宣称已完成 MM92 工程校准。
