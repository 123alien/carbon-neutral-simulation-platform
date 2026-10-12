# ACN-Data 数据质量报告

数据分类：`REAL_PUBLIC`。来源为 ACN-Data 论文作者维护的静态时序仓库，commit `abb7cf15cc7108913e965d4375cc7270d532b65f`。

| 项目 | 结果 |
|---|---:|
| Site | caltech / California_Garage_01 |
| Station | 3 |
| Session | 122 |
| 原始时序采样点 | 359,029 |
| 时间范围（UTC） | 2018-05-01 01:14:30 ～ 2018-05-15 00:15:40 |
| Station 缺失 | 0 |
| ConnectionTime 缺失 | 0 |
| DisconnectTime 缺失 | 0 |
| kWhDelivered 缺失 | 6 |
| 负电量 | 0 |
| Disconnect < Connection | 0 |
| 重复 session ID | 0 |

各 Station 会话数：`2-39-129-17` 39、`2-39-138-29` 42、`2-39-139-28` 41。

静态文件公开的是充电电流、Pilot、累计交付电量等原始时序。本轮保留每个文件对应一个真实会话，`kWhDelivered` 取该文件发布的累计 `Energy Delivered (kWh)` 最大观测值。6 个没有该字段数值的会话保留在 `sessions.csv` 并标记缺失，不进入 DeviceMetric，也没有补 0。

DeviceMetric 使用会话最后一个真实采样时间，指标语义为 `SESSION_TOTAL_AT_DISCONNECT`。它不是小时电量或小时功率，没有拆分成虚构负荷曲线。
