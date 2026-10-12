<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useSiteStore } from "@/stores/site";
import { dashboardApi } from "@/api/dashboard";
import { simulationApi } from "@/api/simulation";
import ScreenHeader from "@/components/screen/ScreenHeader.vue";
import CarbonOverviewPanel from "@/components/screen/CarbonOverviewPanel.vue";
import CentralSpatialPanel from "@/components/screen/CentralSpatialPanel.vue";
import MeasureRecommendationPanel from "@/components/screen/MeasureRecommendationPanel.vue";
import ScenarioRiskPanel from "@/components/screen/ScenarioRiskPanel.vue";
import TrendPanels from "@/components/screen/TrendPanels.vue";
import ScreenPanel from "@/components/screen/ScreenPanel.vue";
import StatusTag from "@/components/StatusTag.vue";
import type {
  Building,
  CarbonTrendResponse,
  DashboardCarbon,
  DashboardEnergy,
  DashboardMarket,
  DashboardMeasure,
  DashboardRecommendation,
  DashboardRisk,
  DashboardScenario,
  DashboardSystemStatus,
  RecommendationRun,
  ScenarioVersion,
  SimulationBatch,
  SiteOverview,
} from "@/types";
const siteStore = useSiteStore(),
  siteId = ref<number | null>(null),
  overview = ref<SiteOverview | null>(null),
  buildings = ref<Building[]>([]),
  carbon = ref<DashboardCarbon>({
    total_t: null,
    scope1_t: null,
    scope2_t: null,
    month_t: null,
    year_t: null,
    per_area_kg_m2: null,
    per_capita_t: null,
    trend: [],
    energy: {},
  }),
  energy = ref<DashboardEnergy>({
    total_energy_kwh: null,
    grid_kwh: null,
    pv_kwh: null,
    wind_kwh: null,
    renewable_rate: null,
    hourly: [],
    task_id: null,
  }),
  measures = ref<DashboardMeasure[]>([]),
  recommendations = ref<DashboardRecommendation[]>([]),
  scenarios = ref<DashboardScenario[]>([]),
  market = ref<DashboardMarket>({ assessment: null, statistics: null }),
  risk = ref<DashboardRisk>({ run: null, high: 0, medium: 0, low: 0 }),
  system = ref<DashboardSystemStatus>({ overview: null, tasks: [] }),
  latestData = ref<string | null>(null),
  panelErrors = ref<Record<string, string>>({}),
  isFullscreen = ref(false);
let businessTimer: number | undefined, systemTimer: number | undefined;
const site = computed(
  () =>
    siteStore.sites.find((x) => x.id === siteId.value) || siteStore.currentSite,
);
const zeroMeasures = [
  "PV",
  "WIND",
  "STORAGE",
  "HVAC",
  "LIGHTING",
  "EV_CHARGER",
  "GREEN_POWER",
] as const;
const ok = <T,>(r: PromiseSettledResult<T>): T | undefined =>
  r.status === "fulfilled" ? r.value : undefined;
const fail = (key: string, r: PromiseSettledResult<unknown>) => {
  if (r.status === "rejected")
    panelErrors.value[key] =
      (r.reason as { message?: string })?.message || "数据请求失败";
  else delete panelErrors.value[key];
};
const sum = (items: number[]) => items.reduce((a, b) => a + b, 0);
async function loadBusiness() {
  if (!site.value) return;
  const s = site.value,
    enterprise = s.enterprise_id,
    now = new Date(),
    yearStart = new Date(now.getFullYear(), 0, 1).toISOString(),
    monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString(),
    end = now.toISOString();
  const [
    ov,
    bs,
    allCarbon,
    monthCarbon,
    yearCarbon,
    batches,
    recs,
    assessments,
    risks,
    enterpriseInfo,
  ] = await Promise.allSettled([
    dashboardApi.siteOverview(s.id),
    dashboardApi.buildings(s.id),
    dashboardApi.siteCarbon(s.id),
    dashboardApi.siteCarbon(s.id, { start_time: monthStart, end_time: end }),
    dashboardApi.siteCarbon(s.id, { start_time: yearStart, end_time: end }),
    dashboardApi.batches(enterprise),
    dashboardApi.recommendations(enterprise),
    dashboardApi.marketAssessments(),
    dashboardApi.risks(),
    simulationApi.enterprise(enterprise),
  ]);
  [
    ["overview", ov],
    ["buildings", bs],
    ["carbon", allCarbon],
    ["batches", batches],
    ["recommendations", recs],
    ["market", assessments],
    ["risk", risks],
  ].forEach(([k, r]) => fail(k as string, r as PromiseSettledResult<unknown>));
  overview.value = ok(ov) || null;
  buildings.value = ok(bs) || [];
  const c = ok(allCarbon) as CarbonTrendResponse | undefined,
    mc = ok(monthCarbon) as CarbonTrendResponse | undefined,
    yc = ok(yearCarbon) as CarbonTrendResponse | undefined,
    total = c?.data_status === "OK" ? c.total_emission_t : null;
  carbon.value = {
    total_t: total,
    scope1_t: c?.scope?.["SCOPE_1"] ?? c?.scope?.["Scope 1"] ?? null,
    scope2_t: c?.scope?.["SCOPE_2"] ?? c?.scope?.["Scope 2"] ?? null,
    month_t: mc?.data_status === "OK" ? mc.total_emission_t : null,
    year_t: yc?.data_status === "OK" ? yc.total_emission_t : null,
    per_area_kg_m2:
      total != null && s.area_m2 ? (total * 1000) / s.area_m2 : null,
    per_capita_t: total != null && s.population ? total / s.population : null,
    trend: c?.trend || [],
    energy: c?.energy || {},
  };
  const batchList = ok(batches) || [],
    batch =
      batchList.find((x) => x.status === "SUCCESS" || x.status === "PARTIAL") ||
      batchList[0];
  await applyBatch(batch);
  applyRecommendations(ok(recs) || []);
  const costs = ok(assessments) || [],
    riskRuns = ok(risks) || [];
  market.value.assessment =
    costs.find((x) => x.task_id === energy.value.task_id) || costs[0] || null;
  const rr =
    riskRuns.find((x) => x.simulation_task_id === energy.value.task_id) ||
    riskRuns[0] ||
    null;
  risk.value = {
    run: rr,
    high: rr?.results.filter((x) => x.level === "HIGH").length || 0,
    medium: rr?.results.filter((x) => x.level === "MEDIUM").length || 0,
    low: rr?.results.filter((x) => x.level === "LOW").length || 0,
  };
  const region = ok(enterpriseInfo)?.region || "全国";
  try {
    market.value.statistics = await dashboardApi.marketStatistics({ region });
  } catch (e) {
    panelErrors.value.market =
      (e as { message?: string }).message || "碳市场数据请求失败";
    market.value.statistics = null;
  }
  latestData.value =
    overview.value?.latest_data_time ||
    energy.value.hourly.at(-1)?.timestamp ||
    null;
}
async function applyBatch(batch: SimulationBatch | undefined) {
  const baselineId = batch?.baseline_scenario_version_id;
  scenarios.value = (batch?.comparison_json?.items || []).map((x) => ({
    ...x,
    name: `场景 V#${x.scenario_version_id}`,
    type: x.scenario_type || "CUSTOM",
    baseline: x.scenario_version_id === baselineId,
  }));
  const item = batch?.items.find((x) => x.status === "SUCCESS" && x.task_id);
  if (!item?.task_id) {
    energy.value = {
      total_energy_kwh: null,
      grid_kwh: null,
      pv_kwh: null,
      wind_kwh: null,
      renewable_rate: null,
      hourly: [],
      task_id: null,
    };
    measures.value = zeroMeasures.map((type) => ({
      type,
      enabled: false,
      summary: "未启用",
      value: null,
    }));
    return;
  }
  try {
    const hourly = await dashboardApi.hourly(item.task_id),
      summary = hourly.task.summary_json || {},
      renewable = Number(summary.renewable_generation_kwh || 0),
      load = Number(summary.load_base_kwh || 0);
    energy.value = {
      total_energy_kwh:
        typeof summary.load_base_kwh === "number"
          ? summary.load_base_kwh
          : null,
      grid_kwh:
        typeof summary.grid_power_kwh === "number"
          ? summary.grid_power_kwh
          : null,
      pv_kwh:
        typeof summary.pv_generation_kwh === "number"
          ? summary.pv_generation_kwh
          : null,
      wind_kwh:
        typeof summary.wind_generation_kwh === "number"
          ? summary.wind_generation_kwh
          : null,
      renewable_rate: load ? renewable / load : null,
      hourly: hourly.results,
      task_id: item.task_id,
    };
    const snapshot = hourly.task.parameter_snapshot_json,
      raw = Array.isArray(snapshot.measures)
        ? (snapshot.measures as Array<{
            measure_type: string;
            parameters_json: Record<string, unknown>;
          }>)
        : [];
    measures.value = zeroMeasures.map((type) => {
      const m = raw.find((x) => x.measure_type === type),
        p = m?.parameters_json || {};
      const key =
          type === "PV"
            ? "capacity_kw"
            : type === "WIND"
              ? "rated_power_kw"
              : type === "STORAGE"
                ? "capacity_kwh"
                : type === "EV_CHARGER"
                  ? "charger_count"
                  : type === "GREEN_POWER"
                    ? "purchase_share"
                    : "saving_rate",
        value = typeof p[key] === "number" ? (p[key] as number) : null;
      return {
        type,
        enabled: Boolean(m),
        value,
        summary: m ? `${key}: ${value ?? "已配置"}` : "未启用",
      };
    });
  } catch (e) {
    panelErrors.value.energy =
      (e as { message?: string }).message || "小时仿真数据失败";
  }
}
function applyRecommendations(runs: RecommendationRun[]) {
  const run = runs[0];
  recommendations.value = (["ECONOMIC", "REDUCTION", "BALANCED"] as const)
    .map(
      (profile) =>
        run?.recommendations
          .filter((x) => x.profile === profile)
          .sort((a, b) => a.rank - b.rank)[0],
    )
    .filter((x): x is NonNullable<typeof x> => Boolean(x))
    .map((x) => ({
      profile: x.profile,
      score: x.score,
      measures: x.measures_json.map((m) => m.type),
      reduction_t: x.metrics_json.estimated_reduction_t ?? null,
      investment: x.metrics_json.investment ?? null,
      payback_years: x.metrics_json.payback_years ?? null,
    }));
}
async function loadSystem() {
  if (!site.value) return;
  const [ov, ts] = await Promise.allSettled([
    dashboardApi.systemOverview(site.value.enterprise_id),
    dashboardApi.systemTasks(site.value.enterprise_id),
  ]);
  fail("system", ov);
  system.value = { overview: ok(ov) || null, tasks: ok(ts) || [] };
}
async function refreshAll() {
  await Promise.all([loadBusiness(), loadSystem()]);
}
function startTimers() {
  stopTimers();
  businessTimer = window.setInterval(loadBusiness, 120000);
  systemTimer = window.setInterval(loadSystem, 60000);
}
function stopTimers() {
  if (businessTimer) clearInterval(businessTimer);
  if (systemTimer) clearInterval(systemTimer);
  businessTimer = systemTimer = undefined;
}
async function selectSite(id: number) {
  siteId.value = id;
  siteStore.selectSite(siteStore.sites.find((x) => x.id === id) || null);
  await refreshAll();
  startTimers();
}
async function toggleFullscreen() {
  if (!document.fullscreenElement)
    await document.documentElement.requestFullscreen();
  else await document.exitFullscreen();
}
const fullscreenChanged = () =>
  (isFullscreen.value = Boolean(document.fullscreenElement));
onMounted(async () => {
  await siteStore.loadSites();
  siteId.value = siteStore.currentSite?.id || null;
  await refreshAll();
  startTimers();
  document.addEventListener("fullscreenchange", fullscreenChanged);
});
onBeforeUnmount(() => {
  stopTimers();
  document.removeEventListener("fullscreenchange", fullscreenChanged);
});
</script>
<template>
  <main v-if="site" class="big-screen">
    <ScreenHeader
      :sites="siteStore.sites"
      :site-id="siteId"
      :backend="system.overview?.health.application_status || 'DOWN'"
      :latest="latestData"
      @site="selectSite"
      @fullscreen="toggleFullscreen"
    />
    <div class="screen-body">
      <aside class="screen-left">
        <CarbonOverviewPanel :data="carbon" /><MeasureRecommendationPanel
          :measures="measures"
          :recommendations="recommendations"
        />
      </aside>
      <section class="screen-center">
        <CentralSpatialPanel
          :site="site"
          :overview="overview"
          :buildings="buildings"
          :hourly="energy.hourly"
        /><ScenarioRiskPanel :scenarios="scenarios" :risk="risk" />
      </section>
      <aside class="screen-right">
        <ScreenPanel
          title="能源与新能源"
          link="/data"
          :empty="energy.total_energy_kwh === null"
          empty-text="暂无仿真数据"
          ><div class="energy-kpis">
            <span
              >总用能 <b>{{ energy.total_energy_kwh ?? "--" }}</b></span
            ><span
              >电网购电 <b>{{ energy.grid_kwh ?? "--" }}</b></span
            ><span
              >PV <b>{{ energy.pv_kwh ?? "--" }}</b></span
            ><span
              >风电 <b>{{ energy.wind_kwh ?? "--" }}</b></span
            ><span
              >可再生占比
              <b>{{
                energy.renewable_rate == null
                  ? "--"
                  : `${(energy.renewable_rate * 100).toFixed(1)}%`
              }}</b></span
            >
          </div></ScreenPanel
        ><ScreenPanel
          title="碳市场分析"
          link="/carbon-market"
          :empty="!market.assessment"
          empty-text="暂无碳市场数据"
          ><div class="market-kpis">
            <span
              >碳价
              <b>{{
                market.assessment?.input_snapshot_json.market
                  .carbon_price_per_t ?? "--"
              }}</b></span
            ><span
              >碳配额
              <b>{{
                market.assessment?.result_json.carbon_quota_t ?? "--"
              }}</b></span
            ><span
              >配额盈亏
              <b>{{
                market.assessment?.result_json.quota_balance_t ?? "--"
              }}</b></span
            ><span
              >CCER
              <b>{{
                market.assessment?.result_json.ccer_offset_t ?? "--"
              }}</b></span
            ><span
              >综合成本
              <b>{{
                market.assessment?.result_json.comprehensive_carbon_cost ?? "--"
              }}</b></span
            ><span
              >净碳排
              <b>{{
                market.assessment?.result_json.net_carbon_emission_t ?? "--"
              }}</b></span
            >
          </div></ScreenPanel
        ><ScreenPanel
          title="系统与数据接入状态"
          link="/system/data-quality"
          :empty="!system.overview"
          ><div class="system-mini">
            <span
              >Backend
              <StatusTag
                :status="
                  system.overview?.health.application_status || 'DOWN'
                " /></span
            ><span
              >Database
              <StatusTag
                :status="
                  system.overview?.health.database_status || 'DOWN'
                " /></span
            ><span
              >数据源正常
              <b>{{ system.overview ? `${system.overview.normal_data_source_count}/${system.overview.data_source_count}` : '--' }}</b></span
            ><span
              >异常数据源
              <b>{{
                system.overview?.abnormal_data_source_count ?? "--"
              }}</b></span
            ><span
              >Provider fallback
              <b>{{
                system.overview?.providers.filter((x) => x.using_fallback)
                  .length ?? "--"
              }}</b></span
            ><span
              >失败任务
              <b>{{
                system.tasks.filter((x) => x.status === "FAILED").length
              }}</b></span
            >
          </div>
          <div class="task-ticker">
            <span
              v-for="t in system.tasks.slice(0, 5)"
              :key="`${t.task_type}-${t.id}`"
              >{{ t.task_type }} #{{ t.id }} · {{ t.status }} ·
              {{
                t.created_at
                  ? new Date(t.created_at).toLocaleString("zh-CN")
                  : "--"
              }}</span
            >
          </div></ScreenPanel
        >
      </aside>
    </div>
    <footer class="screen-bottom">
      <TrendPanels :carbon="carbon" :energy="energy" :market="market" />
    </footer>
    <div v-if="Object.keys(panelErrors).length" class="screen-warnings">
      {{ Object.keys(panelErrors).length }} 个模块暂时不可用，其他区域继续刷新
    </div>
  </main>
  <div v-else class="screen-no-site">
    <span>暂无 Site</span>
    <router-link to="/park?create=site">新增园区</router-link>
  </div>
</template>
