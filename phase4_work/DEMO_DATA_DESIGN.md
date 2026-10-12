# 统一示范园区数据设计

## 数据身份

- 园区：智慧低碳示范园区（`DEMO-PARK-001`）
- 数据性质：`DEMO_SIMULATION`，前端显示“示范仿真数据”
- 时区：`Asia/Shanghai`
- 数据窗口：2024-01-01 00:00 至 2024-12-31 23:00，共 8784 小时
- 本数据仅用于产品演示，不代表真实企业实测或结算数据。

## 对象结构

园区下包含办公楼A、办公楼B、实验楼、综合服务楼；能源系统包含电网、光伏、风电、储能、充电桩、空调和照明。12 台设备、9 个计量点和 8 个数据源均绑定同一园区。

## 生成规律与一致性

- 建筑负荷由工作日、小时、季节和建筑类型共同决定；夜间低、工作日高。
- 空调负荷随室外温度和工作时段变化；照明按办公及夜间时段变化。
- 光伏夜间为零，使用同一小时气象数据的辐照和温度计算。
- 风电由同一小时风速经切入、额定和切出功率曲线计算。
- 充电桩在上下班附近形成峰值。
- 储能逐小时维护荷电状态，谷时充电、峰时放电，受容量、功率和效率约束。
- 电网购电按 `负荷 + 充电 - 放电 - 光伏 - 风电` 计算；所有页面读取持久化后的同一数据，不在页面单独生成随机数。
- 碳核算由同一年度用电及天然气活动数据乘冻结排放因子得到；碳市场序列明确标记为示范仿真数据。

## 初始化

在已配置 `carbon_neutral_dev` 的终端执行：

```powershell
$env:DEMO_MODE='1'
$env:DATABASE_URL=$env:DEV_DATABASE_URL
python scripts/seed_demo_platform.py
```

脚本依次生成确定性 CSV、通过正式服务导入对象与时序数据，并运行核算、四场景批量仿真、推荐、碳成本、风险和 DOCX/PDF 报告。重复执行不会创建第二个同名园区。

## 模块数据来源

| 模块 | 统一来源 |
|---|---|
| 园区管理 | Site、Building、EnergySystem、Device、MeteringPoint |
| 数据接入 | DataSource、DataSourceRuntimeState、DeviceMetric、ValidationLog |
| 碳核算 | CarbonAccountingRun、CarbonAccountingResult |
| 3D全景 | 当前园区概览、建筑、设备、时序指标、核算与仿真结果 |
| 碳中和仿真 | ScenarioVersion、SimulationBatch、SimulationTask、HourlySimulationResult |
| 碳市场 | CarbonMarketTimeseries、CarbonMarketScenario、CarbonCostAssessment |
| 报告中心 | 冻结的 ReportSnapshot 和 ReportFile |

全链结果索引保存在 `demo_data/full_chain_result.json`，生成的报告文件由数据库中的 `report_file` 记录追溯。
