<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useSiteStore } from "@/stores/site";
import { systemApi } from "@/api/system";
import { weatherApi } from "@/api/weather";
import PageHeader from "@/components/PageHeader.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import EmptyState from "@/components/EmptyState.vue";
import ProviderConfig from "@/components/data-config/ProviderConfig.vue";
import ImportWizard from "@/components/data-config/ImportWizard.vue";
import type { ProviderStatus, WeatherSite } from "@/types";
const sites = useSiteStore(),
  providers = ref<ProviderStatus[]>([]),
  weatherSites = ref<WeatherSite[]>([]),
  loading = ref(true),
  error = ref<string | null>(null);
async function load() {
  loading.value = true;
  error.value = null;
  try {
    await sites.loadSites();
    const e = sites.currentSite?.enterprise_id;
    [providers.value, weatherSites.value] = await Promise.all([
      systemApi.providers(e),
      e ? weatherApi.sites(e) : Promise.resolve([]),
    ]);
  } catch (x) {
    error.value =
      (x as { message?: string }).message || "Provider 状态加载失败";
  } finally {
    loading.value = false;
  }
}
const time = (v: string | null) =>
  v ? new Date(v).toLocaleString("zh-CN") : "暂无数据";
const providerName = (value: string) =>
  ({
    WeatherProvider: "气象数据",
    ElectricityPriceProvider: "电价数据",
    GridEmissionFactorProvider: "电网排放因子",
    GreenPowerService: "绿电合同",
  } as Record<string, string>)[value] || value;
onMounted(load);
</script>
<template>
  <section data-testid="system-providers-page">
    <PageHeader
      kicker="系统数据服务"
      title="Provider 管理"
      description="仅配置和导入气象、电价、电网排放因子及绿电服务数据，并明确展示备用模式。"
      ><el-button @click="load">刷新状态</el-button></PageHeader
    ><LoadingState v-if="loading" /><ErrorState
      v-else-if="error"
      :message="error"
      @retry="load"
    /><template v-else-if="sites.currentSite"
      ><section class="provider-grid">
        <article v-for="p in providers" :key="p.provider" class="panel">
          <header>
            <h2>{{ providerName(p.provider) }}</h2>
            <el-tag :type="p.using_fallback ? 'warning' : 'success'">{{
              p.using_fallback ? "当前使用备用模式" : "动态数据可用"
            }}</el-tag>
          </header>
          <dl>
            <dt>记录数</dt>
            <dd>{{ p.record_count }}</dd>
            <dt>最新数据</dt>
            <dd>{{ time(p.latest_data_time) }}</dd>
            <dt>数据范围</dt>
            <dd>{{ time(p.range_start) }} — {{ time(p.range_end) }}</dd>
            <dt>来源</dt>
            <dd>{{ p.source || "暂无来源记录" }}</dd>
          </dl>
        </article>
      </section>
      <article class="panel">
        <h2>数据服务配置</h2>
        <ProviderConfig :site="sites.currentSite" />
      </article>
      <article class="panel">
        <h2>数据服务导入</h2>
        <ImportWizard
          :enterprise-id="sites.currentSite.enterprise_id"
          :weather-sites="weatherSites"
          :allowed-kinds="['WEATHER', 'PRICE', 'GRID_FACTOR']"
          @confirmed="load"
        /></article></template
    ><EmptyState
      v-else
      title="暂无园区/站点"
      description="数据服务配置需要先选择园区/站点"
    />
  </section>
</template>
<style scoped>
.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.provider-grid header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.provider-grid dl {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 8px;
}
.provider-grid dt {
  color: #64748b;
}
</style>
