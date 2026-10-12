# 塞恩室内环境传感器接入说明

## 数据源

- 数据源编码：`IOTSIN_SENSOR`
- 上游地址：`http://iot.iotsin.com`
- 鉴权方式：账号、密码、图形验证码及后端 Session Cookie
- 凭证位置：`.env.external-data`，不进入前端、不提交版本库

## 已接入只读接口

- `POST /sysUser/userLogin`：上游登录
- `GET /device/userDevices`：设备发现
- `GET /group/groupListPage`：分组发现
- `GET /device/deviceWithEnabledFactorsByDeviceAddr`：设备因子
- `GET /sysData/getRealTimeData`：实时数据
- `GET /sysData/multicolumnHistory`：历史数据
- `GET /sysData/getAlarmRecords`：报警记录

平台后端对外提供：

- `GET /api/external-data/iotsin/health`
- `GET /api/external-data/iotsin/captcha`
- `POST /api/external-data/iotsin/login`
- `POST /api/external-data/collect/IOTSIN_SENSOR`
- `GET /api/external-data/iotsin/devices/{device_addr}/factors`
- `POST /api/external-data/iotsin/history`
- `POST /api/external-data/iotsin/alarms`

## 统一模型

实时观测转换为 `source_type/source_id/campus_id/building_id/device_id/device_name/metric_code/metric_name/value/unit/timestamp/quality_status/raw_payload`。未人工确认前，`campus_id` 和 `building_id` 均为空，设备状态为 `UNMAPPED`。

## 2026-09-21 联调事实

- 真实账号登录成功。
- 查询到 4 台设备：`30121063`、`30121065`、`30121066`、`30121067`。
- 4 台设备均处于离线状态，实时观测为 0 条。
- 当前已配置因子均为温度和湿度，尚未发现 CO2 因子。
- 设备经纬度均为 `0,0`，不得用于 GIS 定位。
- 设备上线后再次执行采集即可获取上游实际观测；不得用演示数据冒充实时数据。

## 尚需现场完成

1. 给设备供电并通过配置 App 接入现场 WiFi。
2. 确认设备连接正确的云平台节点和端口。
3. 在上游确认设备状态为在线。
4. 核对 CO2 型号及 CO2 因子是否已启用。
5. 人工确认设备安装位置后，再建立设备与 HBUE 建筑的映射。

