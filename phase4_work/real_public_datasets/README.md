# 公开真实数据验证目录

本目录只保存可核验的公开真实数据及其可复现转换产物。`raw/` 不覆盖，`cleaned/` 不补零、不插值，`normalized/` 对齐平台导入 Schema，`manifests/` 保存 SHA-256 与转换链，`scripts/` 保存可重复执行脚本。

第一轮正式 Validation Site 为 `BDG2 Rat Validation Site`，数据分类为 `REAL_PUBLIC`。它是公开研究数据，不是目标企业内部实测数据；仿真结果是模型输出，不是测量值。中国官方因子和湖北分时政策属于独立的中国市场上下文，不与美国 BDG2 物理园区混用。

执行顺序：

```powershell
python real_public_datasets/scripts/prepare_bdg2_first_round.py
python real_public_datasets/scripts/import_first_round_api.py --api http://127.0.0.1:8000
```

详见 [DATASET_REGISTRY.md](DATASET_REGISTRY.md)、[BDG2_DATA_QUALITY_REPORT.md](BDG2_DATA_QUALITY_REPORT.md)、[REAL_PUBLIC_IMPORT_REPORT.md](REAL_PUBLIC_IMPORT_REPORT.md) 和 [REAL_PUBLIC_CAPABILITY_MATRIX.md](REAL_PUBLIC_CAPABILITY_MATRIX.md)。
