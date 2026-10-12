# 真实数据模型验证总结

本轮采用时间顺序切分：每套 14 天真实数据的前 7 天仅用于校准，后 7 天作为未参与校准的留出验证集。没有删除异常观测、插值或修改真实值。

| 模型 | 留出集版本 | MAE kW | RMSE kW | nRMSE | Energy Error | Correlation |
|---|---|---:|---:|---:|---:|---:|
| Wind | SIMPLE_CURVE | 422.011 | 502.598 | 24.517% | -46.896% | 0.9191 |
| Wind | CALIBRATED_CURVE | 54.513 | 78.079 | 3.809% | -2.076% | 0.9940 |
| PV | legacy POA+NOCT | 8.499 | 13.501 | 11.095% | +41.055% | 0.9925 |
| PV | measured module temperature + calibrated PR | 1.603 | 3.231 | 2.655% | +3.520% | 0.9936 |

生产推荐仍为 Wind `MANUFACTURER_CURVE`，但当前公开 metadata 没有可靠 MM92 厂商曲线，因此 Kelmarsh 验证使用的曲线明确标记 `CALIBRATED`，不能冒充厂商参数。PV 的 PR 同样标记 `CALIBRATED`；逆变器效率与温度系数仍是 `MODEL_DEFAULT`。

统一 `/api/model-validation` 与 `/model-validation` 展示 Observed、Legacy Simulated、Improved Simulated、参数来源、模型版本、数据范围和限制。报告快照增加 `model_validation`，DOCX/PDF 增加“模型验证摘要”章节。
