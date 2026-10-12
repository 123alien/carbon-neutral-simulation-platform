# 湖北经济学院跨镜活动路径展示

所有摄像头为示范布点，不代表真实部署或测绘入口。锚点来自现有真实建筑Polygon边缘附近；校园边界、125栋轮廓和16栋业务绑定未修改。

| 摄像头 | 名称 | 建筑编码 | 经度 | 纬度 |
| --- | --- | --- | --- | --- |
| CAM01 | 教学楼一主入口 | HBUE-B120 | 114.4334643 | 30.4212333 |
| CAM02 | 教学楼二主入口 | HBUE-B119 | 114.4344113 | 30.4216531 |
| CAM03 | 实验楼一主入口 | HBUE-B041 | 114.4308808 | 30.4184864 |
| CAM04 | 行政楼入口 | HBUE-B001 | 114.4275915 | 30.4230251 |
| CAM05 | 枫苑宿舍主入口 | HBUE-B124 | 114.4360668 | 30.4222328 |
| CAM06 | 三清园入口 | HBUE-B009 | 114.4285088 | 30.4233390 |
| CAM07 | 室内体育馆入口 | HBUE-B003 | 114.4279500 | 30.4163546 |
| CAM08 | 大学生活动中心入口 | HBUE-B002 | 114.4287284 | 30.4204263 |

校园编码均为HBUE，floor_id为null，area_id为建筑编码加-DEMO-ENTRY，location_type为DEMO_PLACEMENT。完整映射见 spatial_data/hbue/hbue_demo_cameras.json。

DEMO包含25个匿名编号、25条路径、5类活动；每类5条。活动类型不是身份分类。图层多选使用按Global ID维护的LayerGroup增量增删。像素数据不进入GIS坐标，LIVE未配置位置的节点不绘制；跨区域连线使用适配层segments，避免跳过未配置摄像头强行连线。

接口：POST /api/cross-camera-adapter/paths，参数source=DEMO或LIVE、task_id、video_start_time、allow_demo_fallback。LIVE凭证仅通过后端环境变量CROSS_CAMERA_USERNAME/CROSS_CAMERA_PASSWORD设置，地址通过CROSS_CAMERA_BASE_URL设置，默认http://10.120.203.134:8100。Token仅缓存在后端内存，401后重登一次；请求超时5秒。

LIVE采用内部规范化模型预适配：支持data包装、matches/results列表、tracks/trajectories列表。其他上游字段差异需正式JSON对照完成；未完成对照不宣称真实联调通过。2026-09-16 TCP连通性检查失败，实际LIVE验证待完成。备用数据明确标识DEMO，不将示范轨迹冒充真实结果。

截图：qa_report/hbue-cross-camera-demo.png。

