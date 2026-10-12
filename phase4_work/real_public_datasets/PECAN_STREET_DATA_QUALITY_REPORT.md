# Pecan Street 数据质量报告

## 获取边界

Pecan Street 官方2025年公开数据指南明确推荐其发布者账号下的 Kaggle 样本。该样本包含10户、1分钟、连续3天的 Main Panel、HVAC Condenser、HVAC Fan 和 Solar 电气数据。本次仅选家庭1–3。

公开样本没有 Lighting、Battery/Storage、charge/discharge 或 SOC。更完整的75户分项数据需要 Dataport 大学账号审核；商业用途需要商业许可。因此 Lighting 和 Storage 均为 `BLOCKED_BY_ACCESS`，没有创建假设备或推导 SOC。

## 质量结果

| 项目 | 家庭1 | 家庭2 | 家庭3 |
|---|---:|---:|---:|
| 理论/实际时间点 | 4,321/4,321 | 4,321/4,321 | 4,321/4,321 |
| 完整率 | 100% | 100% | 100% |
| 缺失冷凝机/风机/合计 | 0/0/0 | 0/0/0 | 0/0/0 |
| 冷凝机负功率 | 35 | 94 | 1 |
| HVAC合计负功率 | 0 | 0 | 0 |
| HVAC合计范围 kW | 0.509–4.850 | 0.007–5.130 | 0.009–3.182 |
| 半开区间积分能量 kWh | 194.459 | 143.199 | 142.692 |

家庭+时间戳重复为0。负冷凝机功率作为真实测量基线保留；未裁剪。原始 ZIP SHA-256 为 `7b7ef8abf86c1125e06812ea5227dbc2d04c397618e8cb3b821615b02c41ee5a`，CSV SHA-256 为 `1f7ecc25db0f228273d29fa60c5df84d02df1eb27c27e8409b3033d5cd6fa03f`。

正式 FILE Adapter 写入38,889条：两路观测功率及一条明确标注为 `condenser + fan` 的派生合计。L1/L2/L3 拒绝0、警告0。
