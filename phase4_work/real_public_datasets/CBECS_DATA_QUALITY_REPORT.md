# CBECS 2018 数据质量报告

- 数据集：EIA 2018 CBECS Final Public Use Microdata（官方调查微观数据）
- 数据类别：`REAL_PUBLIC_OFFICIAL`
- 原始记录：6,436 栋抽样建筑；本轮选择 PUBID 1331、1839、4220 三栋匿名建筑
- 时间口径：2018 年年度，不拆分或伪造成月度/小时数据
- 活动记录：12（3 栋 × 电力、天然气、柴油、区域供热）
- 单位：电力 `kWh`；天然气、柴油、区域供热 `thousand Btu (kBtu)`；面积 `ft²` 并另存精确换算的 `m²`
- 完整性：所选四个能源字段 12/12 有效，完整率 100%
- 缺失 / 负值 / 零值：0 / 0 / 0
- 插补：`ZELCNS`、`ZNGCNS`、`ZFKCNS`、`ZDHBTU` 均为 0，所选活动量均非插补值
- 燃油类型：三栋均为 `FKTYPE=2`（Diesel），因此使用 EPA Distillate Fuel Oil No. 2 因子
- 原始 CSV SHA-256：`3e37c81aab2938e63fae47bec837270ba696699aceef904d1326dd25970e7247`
- 官方 codebook SHA-256：`5ee2ccb1ae8a2c4196cdb5e3ffd2be11e877d13cae3474f550306f93e92bd26e`

限制：CBECS 是美国商业建筑抽样调查，公开微观数据经过隐私保护，不能解释为设备级 SCADA、逐时测量或中国企业事实。PUBID 仅作为公开样本标识。
