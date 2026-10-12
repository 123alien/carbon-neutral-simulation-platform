import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { http, silentConfig } from "@/api/http";
import type { HealthStatus } from "@/types";
export interface WorkTab { path: string; title: string; closable: boolean }
export const useAppStore = defineStore("app", () => {
  const loadingCount = ref(0);
  const health = ref<HealthStatus | null>(null);
  const healthError = ref<string | null>(null);
  const sidebarCollapsed = ref(localStorage.getItem("sidebar-collapsed") === "1");
  const tabs = ref<WorkTab[]>([{ path: "/dashboard", title: "综合首页", closable: false }]);
  const loading = computed(() => loadingCount.value > 0);
  function begin() {
    loadingCount.value++;
  }
  function end() {
    loadingCount.value = Math.max(0, loadingCount.value - 1);
  }
  function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value; localStorage.setItem("sidebar-collapsed", sidebarCollapsed.value ? "1" : "0"); }
  function openTab(path: string, title: string) { if (!tabs.value.some((item) => item.path === path)) tabs.value.push({ path, title, closable: path !== "/dashboard" }); }
  function closeTab(path: string) { const index = tabs.value.findIndex((item) => item.path === path); if (index < 0 || !tabs.value[index].closable) return null; tabs.value.splice(index, 1); return tabs.value[Math.min(index, tabs.value.length - 1)]?.path || "/dashboard"; }
  async function checkHealth() {
    try {
      health.value = await http.get<never, HealthStatus>(
        "/health",
        silentConfig,
      );
      healthError.value = null;
    } catch (e) {
      health.value = null;
      healthError.value = (e as { message: string }).message;
    }
    return health.value;
  }
  return {
    loading,
    health,
    healthError,
    sidebarCollapsed,
    tabs,
    begin,
    end,
    checkHealth,
    toggleSidebar,
    openTab,
    closeTab,
  };
});
