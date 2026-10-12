# PV 数据质量报告

## 数据边界

- 数据集：NREL/OEDI PVDAQ System 35，DOI `10.25984/1846021`，`REAL_PUBLIC`。
- 系统：Andre Agassi Preparatory Academy - Gymnasium，Las Vegas, Nevada。
- 范围：2010-10-01 00:00 至 2010-10-14 23:45（America/Los_Angeles），15 分钟；数据库统一 UTC。
- 数据保持原始时间和值；只应用 PVDAQ metrics metadata 中公开的 scale/offset。没有插值、补值或合成测量值。

| 项目 | 结果 |
|---|---:|
| 理论/实际时间记录 | 1,344 / 1,344 |
| 完整率 | 100.00% |
| 重复时间戳 | 0 |
| 缺失 POA / 环境温度 / 组件温度 | 各 1 |
| 缺失 DC / AC 功率 | 0 / 0 |
| 负辐照 | 0 |
| 负 AC 功率 | 718（夜间逆变器待机/测量基线，保留） |
| POA 范围 | 0–1293.164 W/m² |
| AC 功率范围 | -0.9–100.8 kW |

正式链路 `raw → SHA-256 → cleaned → normalized → Preview → L1/L2/L3 → Confirm → PostgreSQL` 完成。FILE Adapter 写入 6,717 条事实，L1/L2/L3 拒绝 0、警告 0。`raw/` 中每个文件的 SHA-256 见 `pvdaq_system35/manifest.json`。
