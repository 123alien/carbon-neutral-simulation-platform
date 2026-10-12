# Pecan Street 导入与验证报告

## 正式接入

独立 `Distributed Energy Validation Site · Pecan Street` 已建立，包含1个 HVAC EnergySystem、3个 HVAC Device、9个 MeteringPoint。链路 `raw → SHA-256 → cleaned → normalized → Preview → L1/L2/L3 → Confirm → PostgreSQL` 完成。

## HVAC

- 实测：冷凝机和风机 Real Power，单位 kW；合计功率为两路实测值的可追溯求和。
- 3户三天半开区间积分能量合计：480.351 kWh；小时/日功率展示使用平均值，能量使用 `kW × interval hours` 积分，未把瞬时功率 SUM。
- 仿真输入验证：排除结束边界孤立点后，将72小时HVAC实测能量作为隔离组件负荷；现有引擎 `load_share=1`，`saving_rate=10%`（`MODEL_PARAMETER_FALLBACK`），输入480.351 kWh，规则输出节能48.035 kWh，守恒误差0。
- 公开文件包含结束边界 `2018-08-26 00:00`。预处理已采用半开区间，避免该点被错误当作额外一小时能量。

## Lighting 与 Storage

公开样本不包含照明、储能充放电或SOC。三项不验证、不创建设备、不从主进线残差推导。状态为 `BLOCKED_BY_ACCESS`。因此SOC连续性、方向、储能能量平衡及Storage模型对比均未声称通过。

## 暴露的问题

1. 当前 HVAC 措施是 `facility_load × static load_share × saving_rate`，不能直接表达逐时真实HVAC子表节能；隔离输入可验证规则，但不是设备级校准。
2. 高频功率边界点进入小时 resample 会生成额外桶；应采用半开时间区间。
3. DeviceMetric 能正确保存kW，但通用查询只能给功率平均值；从功率积分出的kWh需要明确的区间时长语义。

本轮没有修改实测数据或伪造节能率。只补充HVAC功率单位和瞬时聚合支持；设备级真实节能模型仍标记为限制项。
