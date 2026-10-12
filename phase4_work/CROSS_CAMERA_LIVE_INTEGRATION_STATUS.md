# LIVE 跨镜联调记录

## 用户授权的示范空间场景

真实cam1映射教学楼一示范入口HBUE-B120，真实cam2映射教学楼二示范入口HBUE-B119；经纬度复用原CAM01/CAM02校园内锚点。
配置通过现有映射业务服务建立，anchor_source=DEMO_PLACEMENT，不声称录像拍摄于湖北经济学院。
演示时间基准2026-09-09 08:00 +08:00，仅为仿真假设，非核实录像时间。
真实最新任务适配结果：29个Global ID、29组路径、39条区域关联线、0个未映射摄像头。
仅新增2条摄像头映射，不修改125栋轮廓、16栋业务绑定和能源活动数据。
空间配置脚本scripts/configure_cross_camera_demo_context.py可重复执行，已有映射保留。

## 最新认证联调结果

本地私密配置填写后，2026-09-16成功登录，auth/me验证成功，LIVE_READY。
取得27个已完成任务；最新任务20260909_194141_0911e8返回29个匿名Global ID。
真实详细轨迹结构为 cameras / identities[] / tracks[] / points[]。
轨迹字段 camera_id/local_id/start_seconds/end_seconds/observed_seconds/frame_count；点字段 frame/bbox/conf/time_seconds/center/speed_px_s/motion_state/direction。
已按该结构转换相对时间及像素字段，未知字段保留在raw_result/raw_trajectories。
脱敏截取样例位于tests/fixtures/cross_camera_live_redacted.json，不含账号Token或服务器视频路径。
实际camera_id是cam1/cam2，两者均UNMAPPED，因此真实数据已读取但GIS连线尚未展示。
用于本次适配检查的视频起始时间仅为测试时间基准，不代表真实录像时间；正式展示仍需要提供实际video_start_time。
后端自动读取本地.env.cross-camera（进程环境变量优先），需要重启现有后端进程生效。
最新跨镜后端回归9项通过。以下内容是填写凭证前的历史记录。

日期：2026-09-16。

## 实际网络验证

本开发环境 GET http://10.120.203.134:8100/openapi.json 返回 200。
本地进程环境变量及现有开发、测试配置文件均未发现跨镜用户名、密码。
健康检查实测：HTTP 响应正常、服务可达、凭证未配置、登录未成功、Token 未验证。

## 官方服务 OpenAPI 确认（不是认证响应样例）

- POST /api/v1/auth/login：JSON username/password。
- LoginResponse：access_token、token_type、expires_at、user；expires_at 为整数。
- GET /api/v1/auth/me：用于验证 Token；收到401自动重新登录一次。
- GET /api/v1/tasks?limit=100：TaskState 数组，含 task_id/status/created_at。
- GET /api/v1/tasks/{task_id}/result：TaskResult，含 matches、videos、global_mapping、statistics 等。
- MatchRecord：global_id、cam1_local_id、cam2_local_id、similarity、temporal_consistency、combined_score 等，部分值允许为空。
- GET /api/v1/tasks/{task_id}/trajectories?global_id=...：文档只定义 object，具体嵌套结构未公开。

旧解析器的 camera_a_id/local_id_a 等并非当前服务 MatchRecord 字段。新版结构必须等待认证后的样例与详细轨迹一起适配；当前明确阻止将未确认结构伪装成联调成功，不编造分数或摄像头ID。

## 本平台补齐

- GET /api/cross-camera-adapter/health：服务可达、凭证、登录、Token 状态，不返回密码和Token。
- GET /api/cross-camera-adapter/tasks：后端认证读取真实任务列表。
- LIVE 未填写任务时优先 CROSS_CAMERA_TASK_ID，其次真实已完成任务列表。
- Token 按 expires_at 计算缓存有效期，401只重试认证一次。
- 前端LIVE状态展示；失败不自动加载DEMO，切换数据源时移除旧轨迹。
- .env.cross-camera.example 提供配置模板，.gitignore 排除本地环境文件。

## 待完成

需要在后端进程环境配置真实凭证并重启后端。不得通过前端提交密码。
然后读取已有真实任务，保存脱敏响应，确认详细轨迹schema，按原 camera_id 建立空间映射。
此阶段没有认证结果、真实任务ID、Global ID 或 camera_id；LIVE GIS 未验收。
现有125栋轮廓、16栋绑定、8个示范布点、25条示范轨迹不变，未写入或合并上游数据库。

## 回归

跨镜后端测试8项通过；Playwright示范轨迹/筛选/详情/能碳叠加1项通过；vue-tsc与vite生产构建通过（现有大包体积警告）。
