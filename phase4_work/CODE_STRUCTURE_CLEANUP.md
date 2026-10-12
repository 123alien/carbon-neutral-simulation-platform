# 代码结构整理

## 本轮范围

不重写业务架构、不删除业务数据或历史报告。保留接口、迁移记录、本地配置、空间资料与现有算法。

## 清理

- 删除源码目录67份与现有 TypeScript/Vue 源码对应的旧 JavaScript 编译副本，消除模块解析优先使用旧副本的风险。
- 删除 Vite 配置的生成 JavaScript 和声明副本，维护唯一 vite.config.ts；配置类型检查禁止输出文件。
- 删除 hbueFootprintBuildings.ts 内无引用的 surfaceTexture 函数。
- 更新忽略规则，排除构建产物、测试输出、类型检查缓存和重复源码编译副本。

以上生成副本可从保留的源码重新编译，不保留第二套业务代码。

## 大屏职责划分

| 文件 | 职责 |
| --- | --- |
| frontend/src/views/ThreePanoramaView.vue | 当前园区数据协调、页面布局、导航联动 |
| frontend/src/components/screen/DeviceMonitorPanel.vue | 设备排序、状态统计、滚动与暂停、详情事件 |
| frontend/src/assets/panorama.css | 大屏布局及分辨率适配 |
| frontend/src/utils/panoramaFormat.ts | 展示数字格式、中文设备与建筑类型 |
| frontend/src/components/gis/CampusHeatMap.vue | GIS空间底图、建筑热力和图层 |
| frontend/src/components/three/ThreeScene.vue | 三维场景生命周期、拾取、模型组织 |
| frontend/src/utils/campusArchitecture.ts | 核心建筑示意立面及实例批次 |
| frontend/src/utils/hbueFootprintBuildings.ts | 真实轮廓投影、校园环境与轻量背景 |

## 未删除的内容

仍有路由使用的历史页面、后端业务服务、测试、数据表、数据库文件、环境配置、报告和验收资料均保留。根目录历史阶段文档未直接搬迁，以免破坏文档引用；本轮不宣称已完成整个仓库的所有死代码分析。

## 验证结果

- 全量后端：94通过、3跳过，无失败。
- 大屏实时更新、沙盘交互及三种分辨率布局：3项Playwright通过。
- 前端类型检查及生产构建通过；保留现有大包体积警告。
- 构建后 frontend/src 内JavaScript生成副本数量为0。
