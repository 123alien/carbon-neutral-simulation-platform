# Wind 模型改进报告

## 改进

- 保留 `SIMPLE_CURVE` fallback。
- 新增 `MANUFACTURER_CURVE` 和 `CALIBRATED_CURVE` 导入曲线模式，使用分段线性插值且限制在额定功率内。
- 新增基于实测空气密度的等效风速修正；Kelmarsh 无压力观测，因此本轮没有无依据启用。
- cut-in、rated、cut-out 继续可配置。
- 支持 `is_operational` 与 `power_limit_kw`，状态、停机和限功率不再与功率曲线混为一个概念。
- Kelmarsh 发布的部分 Stop 区间与大量正功率同时出现，因此保留展示和分组统计，但不将其直接作为强制停机命令。

## 受控留出集

验证范围 2016-12-25 至 2017-01-01，共 3024 对观测：

| 指标 | SIMPLE_CURVE | CALIBRATED_CURVE |
|---|---:|---:|
| 实测能量 kWh | 452627.420 | 452627.420 |
| 仿真能量 kWh | 240364.243 | 443228.746 |
| MAE kW | 422.011 | 54.513 |
| RMSE kW | 502.598 | 78.079 |
| nRMSE | 24.517% | 3.809% |
| Energy Error | -46.896% | -2.076% |
| Correlation | 0.9191 | 0.9940 |

曲线使用前7天观测按0.5m/s风速箱中位数生成并保持单调，标记 `CALIBRATED`。可靠 MM92 厂商曲线仍缺失，`MANUFACTURER_CURVE` 能力已实现但未声称完成 MM92 厂商曲线验证。
