import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from "vue-router";
const Placeholder = () => import("@/views/PlaceholderView.vue");
const routes: RouteRecordRaw[] = [
  {
    path: "/screen",
    name: "screen",
    component: () => import("@/views/BigScreenView.vue"),
    meta: { title: "综合管理大屏" },
  },
  {
    path: "/3d",
    name: "3d",
    component: () => import("@/views/ThreePanoramaView.vue"),
    meta: { title: "3D全景", icon: "View", dataScope: "site", fullscreen: true },
  },
  {
    path: "/",
    component: () => import("@/layouts/MainLayout.vue"),
    redirect: "/dashboard",
    children: [
      {
        path: "dashboard",
        name: "dashboard",
        component: () => import("@/views/DashboardView.vue"),
        meta: { title: "综合首页", icon: "DataBoard", dataScope: "site" },
      },
      {
        path: "data",
        name: "data",
        component: () => import("@/views/DataAccessView.vue"),
        meta: { title: "数据接入", icon: "Connection", dataScope: "site" },
      },
      {
        path: "device-monitor",
        name: "device-monitor",
        component: () => import("@/views/DeviceMonitorView.vue"),
        meta: { title: "设备监测", icon: "Monitor", dataScope: "site" },
      },
      {
        path: "park",
        name: "park-management",
        component: () => import("@/views/system/SystemObjectsView.vue"),
        meta: { title: "园区管理", icon: "OfficeBuilding", dataScope: "site" },
      },
      {
        path: "carbon",
        name: "carbon",
        component: () => import("@/views/CarbonManagementView.vue"),
        meta: { title: "碳核算", icon: "PieChart", dataScope: "site" },
      },
      {
        path: "carbon-neutral-simulation",
        name: "carbon-neutral-simulation",
        component: () => import("@/views/CarbonNeutralSimulationWorkbench.vue"),
        meta: { title: "碳中和仿真", icon: "Cpu", dataScope: "site" },
      },
      {
        path: "simulation",
        alias: "/workbench/simulation",
        name: "simulation",
        component: () => import("@/views/SimulationView.vue"),
        meta: { title: "仿真推演", icon: "Cpu", dataScope: "site" },
      },
      {
        path: "recommendations",
        name: "recommendations",
        component: () => import("@/views/RecommendationsView.vue"),
        meta: { title: "低碳路径推荐", icon: "Guide", dataScope: "site" },
      },
      {
        path: "scenarios",
        name: "scenarios",
        component: () => import("@/views/ScenariosView.vue"),
        meta: { title: "场景管理", icon: "Files", dataScope: "site" },
      },
      {
        path: "carbon-market",
        name: "carbon-market",
        component: () => import("@/views/CarbonMarketView.vue"),
        meta: { title: "碳市场", icon: "TrendCharts", dataScope: "mixed" },
      },
      {
        path: "model-validation",
        name: "model-validation",
        component: () => import("@/views/ModelValidationView.vue"),
        meta: { title: "模型验证", icon: "DataAnalysis", dataScope: "platform" },
      },
      {
        path: "risks",
        name: "risks",
        component: () => import("@/views/RisksView.vue"),
        meta: { title: "风险评估", icon: "Warning", dataScope: "site" },
      },
      {
        path: "reports",
        name: "reports",
        component: () => import("@/views/ReportsView.vue"),
        meta: { title: "报告中心", icon: "Document", dataScope: "site" },
      },
      {
        path: "workbench/evaluation",
        name: "evaluation-workbench",
        component: () => import("@/views/EvaluationWorkbenchView.vue"),
        meta: { title: "评估与报告", icon: "Document", dataScope: "site" },
      },
      {
        path: "system",
        name: "system",
        component: () => import("@/views/SystemView.vue"),
        meta: { title: "系统管理", icon: "Setting", dataScope: "platform" },
      },
      {
        path: "system/objects",
        name: "system-objects",
        component: () => import("@/views/system/SystemObjectsView.vue"),
        meta: { title: "基础对象管理", icon: "OfficeBuilding", dataScope: "site" },
      },
      {
        path: "system/data-sources",
        name: "system-data-sources",
        component: () => import("@/views/system/SystemDataSourcesView.vue"),
        meta: { title: "数据源管理", icon: "Connection", dataScope: "platform" },
      },
      {
        path: "system/providers",
        name: "system-providers",
        component: () => import("@/views/system/SystemProvidersView.vue"),
        meta: { title: "Provider 管理", icon: "Cloudy", dataScope: "mixed" },
      },
      {
        path: "system/data-quality",
        name: "system-data-quality",
        component: () => import("@/views/system/SystemDataQualityView.vue"),
        meta: { title: "数据质量管理", icon: "CircleCheck", dataScope: "platform" },
      },
    ],
  },
  {
    path: "/:pathMatch(.*)*",
    name: "not-found",
    component: () => import("@/views/NotFoundView.vue"),
    meta: { title: "页面未找到" },
  },
];
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});
router.beforeEach((to)=>to.path==="/data"&&to.query.setup?{path:"/park",query:{create:"site"}}:true);
router.afterEach((to) => {
  document.title = `${String(to.meta.title || "平台")} | 碳中和仿真推演平台`;
});
export default router;
export const menuRoutes = routes[0].children || [];
