# 真实外部数据接入第一阶段

日期：2026-09-16。

## 实际验收状态

气象站HTTP200、code=0、online=true。首次请求16个属性，入库采集时17个属性。
真实结构：code/data/msg，data包含deviceId/productKey/dn/identifier2property/online/onlineTime/offlineTime。
属性包含identifier/dataType/name/accessMode/description/unit/time/value。
所有17个属性value/time均为空，0条有效观测；不可用于替换示范气象或进行真实碳核算。
原始响应保存在数据库STATE记录，脱敏样例tests/fixtures/weather_station_real_redacted.json。
实际字段按上游identifier原样标准化，不把Lux当W/m²，不补辐照度、不补缺失值。

物联网云平台未配置IOT_CLOUD_LOGIN_NAME/IOT_CLOUD_PASSWORD，未获取Token、分组、设备或真实因子列表。
登录、鉴权重试、设备发现、实时/指定设备/历史/报警读取代码已实现；物联网协议结构测试不是认证后的真实集成验收。
列表暂识别数组或data数组，未识别时保留原始响应并提示待联调，不猜测层级。
在线/离线枚举尚未取得，因此不猜测deviceStatus语义，数量显示未确认。

## 配置及接口

本地.env或.env.external-data读取，进程变量优先；模板.env.external-data.example。
物联网账号不是跨镜系统账号。密码及Token仅供后端，前端不调用第三方。
提供方接口为HTTP且登录使用GET参数，传输本身没有TLS保护；生产接入须由提供方启用HTTPS或安全专网。当前不能宣称安全传输已验证。

- GET /api/external-data/status
- POST /api/external-data/collect/IOT_CLOUD
- POST /api/external-data/collect/WEATHER_STATION
- GET /api/external-data/records?source_type=...&kind=DEVICE或METRIC
- GET /api/external-data/realtime/{device_addr}
- POST /api/external-data/history（deviceAddr/nodeId/startTime/endTime）
- GET /api/external-data/alarms

读取接口有固定白名单，没有删除历史或继电器控制能力。

## 数据模型和隔离

新增external_data_record暂存表，迁移022_external_data_staging。
source_type为IOT_CLOUD/WEATHER_STATION，record_kind为DEVICE/METRIC/RAW/STATE。
DEVICE保存待映射配置：upstream_device_id/upstream_device_name/source_type/campus_id/building_id/energy_type/metric_mapping/enabled，建筑校园为空且enabled=false。
METRIC保存source_type/source_id/campus_id/building_id/device_id/device_name/metric_code/metric_name/value/unit/timestamp/quality_status/raw_payload。
原始单位、因子及设备坐标原样保留，坐标系统未确认前不绘制GIS。没有应用coefficient/offset，须确认上游value是否已换算后再处理，防止重复缩放。
观测时间为epoch或带时区ISO时转UTC；无时区时间标记未验证，不凭空假设。
相同设备/指标/时间/值校验散列去重。缺值属性是字段/质量记录，不是有效DeviceMetric事实。
待映射真实数据不写入校园DeviceMetric、核算或仿真；后续人工绑定后复用既有正式接入和L1/L2/L3管道。
现有示范数据、125栋GIS轮廓、16栋业务绑定、跨镜适配与示范轨迹保持不变。
本阶段没有自动定时轮询，仅提供后端采集触发；持续采集需在凭证和协议确认后挂接现有调度能力。

## 页面及测试

数据接入页面增加真实数据接入状态、待绑定设备和最新指标查看。
全量pytest：90 passed、3 skipped；Playwright外部状态与跨镜轨迹2 passed；vue-tsc/vite构建通过（现有体积警告）。
截图qa_report/external-data-status.png为接口夹具UI测试截图，非云平台真实设备清单。

## 修改文件

app/models/external_data.py、app/services/external_data_service.py、app/api/routes/external_data.py、app/main.py、alembic/versions/022_external_data_staging.py。
frontend/src/components/data-config/ExternalDataStatus.vue、frontend/src/views/DataAccessView.vue。
tests/test_external_data.py、tests/fixtures/weather_station_real_redacted.json、frontend/e2e/external-data-status.spec.ts、本地配置及模板。
