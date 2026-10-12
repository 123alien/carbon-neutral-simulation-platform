<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import * as Icons from "@element-plus/icons-vue";
import { useAppStore } from "@/stores/app";
import { useSiteStore } from "@/stores/site";
const route = useRoute();
const router = useRouter();
const app = useAppStore();
const sites = useSiteStore();
const title = computed(() => String(route.meta.title || ""));
const icon = (name: unknown) => Icons[String(name) as keyof typeof Icons];
const aboutVisible = ref(false);
const versionVisible = ref(false);
const isDemoSite = computed(() =>
  sites.currentSite?.metadata_json?.data_class === "DEMO_SIMULATION"
  || sites.currentSite?.metadata_json?.demo === true,
);
const groups = [{title:"",items:[
  {path:"/dashboard",title:"综合首页",icon:"DataBoard"},
  {path:"/park",title:"园区管理",icon:"OfficeBuilding"},
  {path:"/data",title:"数据接入",icon:"Connection"},
  {path:"/device-monitor",title:"设备监测",icon:"Monitor"},
  {path:"/carbon",title:"碳核算",icon:"PieChart"},
  {path:"/3d",title:"3D全景",icon:"View"},
  {path:"/carbon-neutral-simulation",title:"碳中和仿真",icon:"Cpu"},
  {path:"/carbon-market",title:"碳市场",icon:"TrendCharts"},
  {path:"/reports",title:"报告中心",icon:"Document"},
]}];
async function closeTab(path: string) {
  const next = app.closeTab(path);
  if (route.path === path && next) await router.push(next);
}
async function userAction(command: string) {
  if (command === "system") await router.push("/system");
  else if (command === "about") aboutVisible.value = true;
  else versionVisible.value = true;
}
async function fullscreen() {
  if (!document.fullscreenElement)
    await document.documentElement.requestFullscreen();
  else await document.exitFullscreen();
}
watch(
  () => route.fullPath,
  () => app.openTab(route.fullPath, String(route.meta.title || "页面")),
  { immediate: true },
);
onMounted(() => {
  app.checkHealth();
  sites.loadSites().catch(() => undefined);
});
</script>
<template>
  <el-container class="shell"
    ><el-aside :width="app.sidebarCollapsed ? '72px' : '248px'" class="sidebar"
      ><div class="brand">
        <div class="brand-mark">C</div>
        <div v-if="!app.sidebarCollapsed">
          <strong>碳智推演</strong><span>Carbon Simulation</span>
        </div>
      </div>
      <el-menu
        router
        :default-active="route.path"
        :collapse="app.sidebarCollapsed"
        class="nav-menu"
        ><template v-for="group in groups" :key="group.title"
          ><div
            v-if="group.title && !app.sidebarCollapsed"
            class="nav-group-title"
          >
            {{ group.title }}
          </div>
          <el-menu-item
            v-for="item in group.items"
            :key="item.path"
            :index="item.path"
            ><el-icon><component :is="icon(item.icon)" /></el-icon
            ><template #title>{{ item.title }}</template></el-menu-item
          ></template
        ></el-menu
      ><button
        class="collapse-btn"
        :aria-label="app.sidebarCollapsed ? '展开导航' : '收起导航'"
        data-testid="sidebar-toggle"
        @click="app.toggleSidebar"
      >
        <el-icon
          ><component
            :is="app.sidebarCollapsed ? Icons.Expand : Icons.Fold" /></el-icon
        ><span v-if="!app.sidebarCollapsed">收起导航</span>
      </button></el-aside
    ><el-container
      ><el-header class="topbar"
        ><div class="top-left">
          <el-button
            text
            :icon="app.sidebarCollapsed ? Icons.Expand : Icons.Fold"
            aria-label="切换导航"
            @click="app.toggleSidebar"
          /><el-breadcrumb separator="/"
            ><el-breadcrumb-item>平台</el-breadcrumb-item
            ><el-breadcrumb-item>{{ title }}</el-breadcrumb-item></el-breadcrumb
          >
          <span v-if="route.meta.dataScope==='site'&&sites.currentSite" class="context-chip"
            >园区/单位：{{ sites.currentSite.name }}</span
          >
          <span v-if="isDemoSite" class="context-chip demo-chip">示范仿真数据</span>
          <span v-else-if="route.meta.dataScope==='platform'" class="context-chip">平台范围 · 全部园区</span>
          <span v-else-if="route.meta.dataScope==='mixed'" class="context-chip">公共市场数据与当前园区情景</span>
          <span v-if="route.query.scenario_version" class="context-chip">场景版本 · #{{route.query.scenario_version}}</span>
          <span v-if="route.query.task" class="context-chip">仿真任务 · #{{route.query.task}}</span>
        </div>
        <div class="top-actions">
          <div class="health-pill" :class="app.health ? 'online' : 'offline'">
            <span></span
            >{{
              app.health ? `后端在线 · ${app.health.version}` : "后端未连接"
            }}
          </div>
          <el-tooltip content="切换全屏"
            ><el-button
              circle
              :icon="Icons.FullScreen"
              aria-label="切换全屏"
              @click="fullscreen"
          /></el-tooltip>
          <el-dropdown trigger="click" @command="userAction"
            ><el-avatar class="admin-avatar" :size="34" data-testid="admin-menu"
              >管</el-avatar
            ><template #dropdown
              ><el-dropdown-menu
                ><el-dropdown-item disabled>管理员</el-dropdown-item
                ><el-dropdown-item command="system"
                  >系统设置 / 运行状态</el-dropdown-item
                ><el-dropdown-item command="about">关于平台</el-dropdown-item
                ><el-dropdown-item command="version"
                  >版本信息</el-dropdown-item
                ></el-dropdown-menu
              ></template
            ></el-dropdown
          >
        </div></el-header
      >
      <div class="work-tabs">
        <button
          v-for="tab in app.tabs"
          :key="tab.path"
          :class="{ active: route.fullPath === tab.path }"
          @click="router.push(tab.path)"
        >
          {{ tab.title
          }}<span
            v-if="tab.closable"
            role="button"
            :aria-label="`关闭 ${tab.title}`"
            @click.stop="closeTab(tab.path)"
            >×</span
          >
        </button>
      </div>
      <el-main class="main">
        <router-view v-slot="{ Component }"
          ><transition name="fade" mode="out-in"
            ><component :is="Component" /></transition></router-view></el-main
    ></el-container>
    <div v-if="app.loading" class="global-loading">
      <el-icon class="is-loading"><Icons.Loading /></el-icon
      ><span>正在加载平台数据</span>
    </div></el-container
  >
  <el-dialog v-model="aboutVisible" title="关于平台" width="440px"
    ><el-descriptions :column="1" border
      ><el-descriptions-item label="系统名称"
        >碳中和仿真推演平台</el-descriptions-item
      ><el-descriptions-item label="定位"
        >政企碳中和科研与管理平台</el-descriptions-item
      ></el-descriptions
    ></el-dialog
  >
  <el-dialog v-model="versionVisible" title="版本信息" width="440px"
    ><el-descriptions :column="1" border
      ><el-descriptions-item label="前端">V1.0.0-beta.15</el-descriptions-item
      ><el-descriptions-item label="后端">{{
        app.health?.version || "未连接"
      }}</el-descriptions-item
      ><el-descriptions-item label="数据库版本"
        >019_park_centered_data_sources</el-descriptions-item
      ></el-descriptions
    ></el-dialog
  >
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
}

.nav-menu {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
}

.collapse-btn {
  position: static;
  flex: 0 0 40px;
  width: auto;
  margin: 8px 12px 16px;
}

.demo-chip {
  color: #7a4b00;
  border-color: #f1c56e;
  background: #fff7df;
}
</style>
