<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { EChartsOption } from "echarts";
import { useRoute, useRouter } from "vue-router";
import { useSiteStore } from "@/stores/site";
import { sitesApi } from "@/api/sites";
import { devicesApi } from "@/api/devices";
import { carbonApi } from "@/api/carbon";
import { simulationApi } from "@/api/simulation";
import { http, silentConfig } from "@/api/http";
import ThreeScene from "@/components/three/ThreeScene.vue";
import CampusHeatMap from "@/components/gis/CampusHeatMap.vue";
import BaseChart from "@/components/BaseChart.vue";
import DeviceMonitorPanel from "@/components/screen/DeviceMonitorPanel.vue";
import {
  formatPanoramaNumber as fmt,
  panoramaTypeName as typeName,
} from "@/utils/panoramaFormat";
import type {
  Building,
  CarbonTrendResponse,
  Device,
  HourlySimulationPoint,
  SiteOverview,
  TelemetryResponse,
} from "@/types";

const route = useRoute(),
  router = useRouter(),
  store = useSiteStore();
const siteId = ref<number>(),
  overview = ref<SiteOverview | null>(null),
  buildings = ref<Building[]>([]),
  devices = ref<Device[]>([]),
  hourly = ref<HourlySimulationPoint[]>([]),
  carbon = ref<CarbonTrendResponse | null>(null),
  buildingCarbon = ref<Array<{ building: Building; emission: number }>>([]),
  selected = ref<Building | Device | null>(null),
  telemetry = ref<TelemetryResponse | null>(null),
  period = ref<"24H" | "7D" | "ALL">("24H"),
  timeIndex = ref(0),
  loading = ref(false),
  error = ref(""),
  now = ref(new Date()),
  spatialView = ref<"GIS" | "THREE">("GIS"),
  heatMetric = ref<"CARBON" | "ENERGY">("CARBON");
const site = computed(() => store.sites.find((x) => x.id === siteId.value));
const liveSnapshot = ref<{
  timestamp: string;
  data_notice: string;
  clean_reduction_t: number;
  current: HourlySimulationPoint;
  buildings: Array<{
    id: number;
    emission_t: number;
    energy_kwh: number;
    water_m3: number;
    power_kw: number;
    hvac_power_kw: number;
    lighting_power_kw: number;
  }>;
} | null>(null);
let refreshing = false;
const liveError = ref("");
async function refreshLive() {
  if (site.value?.code !== "HBUE" || refreshing) return;
  const id = site.value.id;
  refreshing = true;
  try {
    const data = (await http.get(
      `/api/result-interface/campuses/${id}/live-demo?history_hours=${period.value === "ALL" ? 8784 : 168}`,
      silentConfig,
    )) as unknown as typeof liveSnapshot.value & {
      hourly: HourlySimulationPoint[];
      trend: CarbonTrendResponse["trend"];
      total_emission_t: number;
    };
    if (site.value?.id !== id || !data?.current || !Array.isArray(data.hourly))
      return;
    const following = timeIndex.value >= hourly.value.length - 1;
    liveSnapshot.value = data;
    hourly.value = [...data.hourly, data.current];
    liveError.value = "";
    buildings.value = buildings.value.map((b) => {
      const r = data.buildings.find((x) => x.id === b.id);
      return r
        ? {
            ...b,
            metadata_json: {
              ...b.metadata_json,
              annual_energy_kwh: r.energy_kwh,
              annual_water_m3: r.water_m3,
              annual_emission_tco2e: r.emission_t,
              live_power_kw: r.power_kw,
              live_hvac_power_kw: r.hvac_power_kw,
              live_lighting_power_kw: r.lighting_power_kw,
              data_notice: "示范仿真数据（本年截至当前时间）",
              live_timestamp: data.timestamp,
            },
          }
        : b;
    });
    if (selected.value && "building_type" in selected.value)
      selected.value =
        buildings.value.find((b) => b.id === selected.value?.id) || null;
    if (following) timeIndex.value = Math.max(0, hourly.value.length - 1);
    carbon.value = {
      ...carbon.value,
      total_emission_t: data.total_emission_t,
      trend: data.trend,
    } as CarbonTrendResponse;
    buildingCarbon.value = data.buildings
      .flatMap((r) => {
        const b = buildings.value.find((x) => x.id === r.id);
        return b ? [{ building: b, emission: r.emission_t }] : [];
      })
      .sort((a, b) => a.emission - b.emission)
      .slice(-6);
  } catch {
    liveError.value = liveSnapshot.value
      ? "更新失败，保留上次快照"
      : "实时仿真暂不可用，请重新加载";
  } finally {
    refreshing = false;
  }
}
const points = computed(() =>
  period.value === "24H"
    ? hourly.value.slice(-24)
    : period.value === "7D"
      ? hourly.value.slice(-168)
      : hourly.value,
);
const sum = (key: keyof HourlySimulationPoint) =>
  points.value
    .filter(
      (x) =>
        !liveSnapshot.value || x.timestamp !== liveSnapshot.value.timestamp,
    )
    .reduce((n, x) => n + Number(x[key] || 0), 0);
const totalCarbon = computed(() => carbon.value?.total_emission_t ?? null);
const currentCarbon = computed(() =>
  points.value.length
    ? sum("carbon_emission_t")
    : (overview.value?.latest_carbon_emission_t ?? null),
);
const selectedPoint = computed(() => hourly.value[timeIndex.value]);
const currentLoad = computed(() =>
  points.value.length
    ? Number(selectedPoint.value?.load_after_saving_kwh || 0) +
      Number(selectedPoint.value?.ev_charging_load_kwh || 0)
    : null,
);
const grid = computed(() =>
  points.value.length ? Number(selectedPoint.value?.grid_power_kwh || 0) : null,
);
const renewableRatio = computed(() => {
  const demand = sum("load_after_saving_kwh") + sum("ev_charging_load_kwh");
  return demand ? (sum("renewable_generation_kwh") / demand) * 100 : null;
});
const storageSoc = computed(() =>
  points.value.length
    ? Number(selectedPoint.value?.storage_soc_kwh || 0)
    : null,
);
const axis = () =>
  points.value.map((x) =>
    new Date(x.timestamp).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
    }),
  );
const line = (
  names: Array<[string, keyof HourlySimulationPoint, string]>,
): EChartsOption => ({
  tooltip: { trigger: "axis" },
  legend: {
    type: "scroll",
    itemWidth: 12,
    itemHeight: 8,
    textStyle: { color: "#8db9c7" },
  },
  grid: { left: 44, right: 18, top: 30, bottom: 24 },
  xAxis: {
    type: "category",
    data: axis(),
    axisLabel: { color: "#6f9baa" },
    axisLine: { lineStyle: { color: "#1c5362" } },
  },
  yAxis: {
    type: "value",
    splitNumber: 3,
    axisLabel: { color: "#6f9baa" },
    splitLine: { lineStyle: { color: "#123b48" } },
  },
  series: names.map(([name, key, color]) => ({
    name,
    type: "line",
    smooth: true,
    showSymbol: false,
    data: points.value.map((x) => Number(x[key] || 0)),
    lineStyle: { color },
    areaStyle: { color: `${color}22` },
  })),
});
const energyOption = computed(() =>
  line([
    ["当前负荷", "load_after_saving_kwh", "#43e0ca"],
    ["电网购电", "grid_power_kwh", "#46a8ff"],
    ["可再生能源", "renewable_generation_kwh", "#ffd166"],
  ]),
);
const generationOption = computed(() =>
  line([
    ["光伏发电", "pv_generation_kwh", "#ffd166"],
    ["风电发电", "wind_generation_kwh", "#59b8ff"],
  ]),
);
const carbonOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: "axis" },
  grid: { left: 45, right: 18, top: 12, bottom: 24 },
  xAxis: {
    type: "category",
    data: carbon.value?.trend.map((x) => x.timestamp) || [],
    axisLabel: {
      color: "#6f9baa",
      formatter: (value: string) => value.slice(0, 7),
    },
  },
  yAxis: {
    type: "value",
    splitNumber: 3,
    axisLabel: { color: "#6f9baa" },
    splitLine: { lineStyle: { color: "#123b48" } },
  },
  series: [
    {
      type: "line",
      smooth: true,
      showSymbol: false,
      data: carbon.value?.trend.map((x) => x.emission_t) || [],
      lineStyle: { color: "#ff806b" },
      areaStyle: { color: "#ff806b22" },
    },
  ],
}));
const rankOption = computed<EChartsOption>(() => ({
  grid: { left: 78, right: 20, top: 8, bottom: 20 },
  xAxis: {
    type: "value",
    axisLabel: { color: "#6f9baa" },
    splitLine: { lineStyle: { color: "#123b48" } },
  },
  yAxis: {
    type: "category",
    data: buildingCarbon.value.map((x) => x.building.name),
    axisLabel: { color: "#b9dce4" },
  },
  series: [
    {
      type: "bar",
      data: buildingCarbon.value.map((x) => x.emission),
      itemStyle: { color: "#ff806b" },
    },
  ],
}));
const telemetryOption = computed<EChartsOption>(() => ({
  tooltip: { trigger: "axis" },
  grid: { left: 42, right: 12, top: 16, bottom: 28 },
  xAxis: {
    type: "category",
    data: telemetry.value?.data.map((x) => x.timestamp) || [],
    axisLabel: { color: "#6f9baa" },
  },
  yAxis: {
    type: "value",
    axisLabel: { color: "#6f9baa" },
    splitLine: { lineStyle: { color: "#123b48" } },
  },
  series: [
    {
      type: "line",
      showSymbol: false,
      smooth: true,
      data: telemetry.value?.data.map((x) => x.value) || [],
      lineStyle: { color: "#43e0ca" },
    },
  ],
}));

async function loadData() {
  if (!site.value) return;
  loading.value = true;
  error.value = "";
  selected.value = null;
  try {
    const [ov, bs, ds, c, batches] = await Promise.all([
      sitesApi.overview(site.value.id),
      sitesApi.buildings(site.value.id),
      devicesApi.bySite(site.value.id),
      carbonApi.site(site.value.id),
      simulationApi.batches(site.value.enterprise_id),
    ]);
    overview.value = ov;
    buildings.value = bs;
    devices.value = ds;
    carbon.value = c;
    const ids = batches
      .flatMap((b) => b.items)
      .map((x) => x.task_id)
      .filter((x): x is number => Boolean(x));
    const requested = Number(route.query.task),
      taskId = ids.includes(requested) ? requested : ids.at(-1);
    hourly.value = taskId
      ? (await simulationApi.getHourly(taskId)).results
      : [];
    timeIndex.value = Math.max(0, hourly.value.length - 1);
    const ranks = await Promise.all(
      bs.map(async (building) => {
        try {
          const result = await carbonApi.building(building.id);
          return result.total_emission_t === null
            ? null
            : { building, emission: result.total_emission_t };
        } catch {
          return null;
        }
      }),
    );
    buildingCarbon.value = ranks
      .filter((x): x is { building: Building; emission: number } => x !== null)
      .sort((a, b) => a.emission - b.emission)
      .slice(-6);
  } catch (e) {
    error.value = (e as { message?: string }).message || "园区全景数据加载失败";
  } finally {
    loading.value = false;
  }
}
async function chooseBuilding(b: Building) {
  selected.value = b;
  telemetry.value = null;
}
async function chooseDevice(d: Device) {
  selected.value = d;
  try {
    telemetry.value = await devicesApi.telemetry(d.id);
  } catch {
    telemetry.value = null;
  }
}
async function toggleFullscreen() {
  if (document.fullscreenElement) await document.exitFullscreen();
  else await document.documentElement.requestFullscreen();
}
let clock = 0;
let liveTimer = 0;
onMounted(async () => {
  await store.loadSites();
  const q = Number(route.query.site),
    hbue = store.sites.find((x) => x.code === "HBUE");
  siteId.value = store.sites.some((x) => x.id === q)
    ? q
    : (hbue?.id ?? store.currentSite?.id);
  clock = window.setInterval(() => (now.value = new Date()), 1000);
});
onMounted(() => {
  liveTimer = window.setInterval(() => {
    void refreshLive();
  }, 15000);
});
onBeforeUnmount(() => {
  window.clearInterval(clock);
  window.clearInterval(liveTimer);
});
watch(period, () => {
  void refreshLive();
});
watch(siteId, async (id) => {
  liveSnapshot.value = null;
  const s = store.sites.find((x) => x.id === id);
  if (s) store.selectSite(s);
  await loadData();
  await refreshLive();
});
</script>
<style scoped src="@/assets/panorama.css"></style>
<template>
  <aside
    v-if="liveSnapshot"
    class="live-source-notice"
    data-testid="campus-live-notice"
  >
    示范仿真数据 · 本年累计与当前运行快照 · 更新时间：{{
      new Date(liveSnapshot.timestamp).toLocaleString("zh-CN")
    }}<span v-if="liveError"> · {{ liveError }}</span>
  </aside>
  <main class="panorama-screen" data-testid="panorama-screen">
    <header class="panorama-screen-head">
      <button class="back-button" @click="router.push('/dashboard')">
        ← 返回业务平台
      </button>
      <div>
        <h1>园区碳能三维全景</h1>
        <p>空间、能源、碳排放与设备运行一体化监测</p>
      </div>
      <div class="head-controls">
        <el-select v-model="siteId" placeholder="选择园区"
          ><el-option
            v-for="s in store.sites"
            :key="s.id"
            :label="s.name"
            :value="s.id" /></el-select
        ><button @click="toggleFullscreen">全屏显示</button
        ><time>{{ now.toLocaleString("zh-CN") }}</time>
      </div>
    </header>
    <div v-if="error" class="screen-message">
      <b>数据加载失败</b><span>{{ error }}</span
      ><button @click="loadData">重新加载</button>
    </div>
    <div v-else-if="loading" class="screen-message">正在加载园区全景数据…</div>
    <div v-else-if="site" class="panorama-dashboard">
      <section class="visual-panel left-top">
        <h2>碳排放总览</h2>
        <div class="metric-grid">
          <button @click="router.push('/carbon')">
            <span>累计碳排放</span
            ><b>{{ fmt(totalCarbon) }}<small> 吨</small></b></button
          ><button @click="router.push('/carbon')">
            <span>当前时段碳排放</span
            ><b>{{ fmt(currentCarbon) }}<small> 吨</small></b></button
          ><button>
            <span>清洁能源减排量</span
            ><b
              >{{
                fmt(
                  liveSnapshot
                    ? liveSnapshot.clean_reduction_t
                    : points.length
                      ? sum("green_power_carbon_reduction_t")
                      : null,
                )
              }}<small> 吨</small></b
            ></button
          ><button>
            <span>数据完整率</span
            ><b
              >{{
                fmt(
                  overview?.data_completeness_rate == null
                    ? null
                    : overview.data_completeness_rate * 100,
                )
              }}<small v-if="overview?.data_completeness_rate != null"
                >%</small
              ></b
            >
          </button>
        </div>
        <h3>碳排趋势</h3>
        <BaseChart
          :option="carbonOption"
          :empty="!carbon?.trend.length"
          height="190px"
        />
      </section>
      <section class="visual-panel left-bottom">
        <h2>建筑碳排排名</h2>
        <BaseChart
          :option="rankOption"
          :empty="!buildingCarbon.length"
          height="210px"
        />
        <div class="rank-buttons">
          <button
            v-for="x in [...buildingCarbon].reverse()"
            :key="x.building.id"
            @click="chooseBuilding(x.building)"
          >
            {{ x.building.name }}<b>{{ fmt(x.emission) }} 吨</b>
          </button>
        </div>
      </section>
      <section class="scene-stage">
        <div class="scene-caption">
          <div>
            <span>当前空间场景</span>
            <h2>
              {{
                spatialView === "GIS" ? "湖北经济学院 GIS 热力图" : site.name
              }}
            </h2>
            <small
              >建筑 {{ buildings.length }} · 设备 {{ devices.length }} · 异常
              {{ overview?.anomaly_count ?? "暂无数据" }}</small
            >
          </div>
          <div class="scene-controls">
            <div class="view-switch">
              <button
                :class="{ active: spatialView === 'GIS' }"
                @click="spatialView = 'GIS'"
              >
                GIS热力</button
              ><button
                :class="{ active: spatialView === 'THREE' }"
                @click="spatialView = 'THREE'"
              >
                三维园区
              </button>
            </div>
            <div v-if="spatialView === 'GIS'" class="view-switch">
              <button
                :class="{ active: heatMetric === 'CARBON' }"
                @click="heatMetric = 'CARBON'"
              >
                碳排放</button
              ><button
                :class="{ active: heatMetric === 'ENERGY' }"
                @click="heatMetric = 'ENERGY'"
              >
                综合能耗
              </button>
            </div>
            <div class="time-switch">
              <button
                v-for="p in [
                  { k: '24H', n: '近24小时' },
                  { k: '7D', n: '近7天' },
                  { k: 'ALL', n: '全部' },
                ]"
                :key="p.k"
                :class="{ active: period === p.k }"
                @click="period = p.k as typeof period"
              >
                {{ p.n }}
              </button>
            </div>
          </div>
        </div>
        <div class="spatial-viewport">
          <CampusHeatMap
            v-if="spatialView === 'GIS'"
            :buildings="buildings"
            :building-carbon="buildingCarbon"
            :metric="heatMetric"
            @building="chooseBuilding"
          /><ThreeScene
            v-else
            :site="site"
            :buildings="buildings"
            :devices="devices"
            :hourly="hourly"
            :time-index="timeIndex"
            @building="chooseBuilding"
            @device="chooseDevice"
          />
        </div>
        <div class="scene-kpis">
          <div>
            <span>当前负荷</span><b>{{ fmt(currentLoad) }} kW</b>
          </div>
          <div>
            <span>电网购电</span><b>{{ fmt(grid) }} kW</b>
          </div>
          <div>
            <span>可再生能源占比</span><b>{{ fmt(renewableRatio) }}%</b>
          </div>
          <div>
            <span>储能荷电量</span><b>{{ fmt(storageSoc) }} kWh</b>
          </div>
        </div>
        <div class="timeline">
          <span>{{ hourly[timeIndex]?.timestamp || "暂无小时仿真结果" }}</span
          ><el-slider
            v-model="timeIndex"
            :min="0"
            :max="Math.max(0, hourly.length - 1)"
            :disabled="!hourly.length"
            :show-tooltip="false"
          />
        </div>
      </section>
      <section class="visual-panel right-top">
        <h2>能源运行态势</h2>
        <BaseChart
          :option="energyOption"
          :empty="!points.length"
          height="205px"
        />
        <div class="energy-strip">
          <span
            >光伏发电<b
              >{{ fmt(points.length ? sum("pv_generation_kwh") : null) }} kWh</b
            ></span
          ><span
            >风电发电<b
              >{{
                fmt(points.length ? sum("wind_generation_kwh") : null)
              }}
              kWh</b
            ></span
          ><span
            >储能充/放<b
              >{{ fmt(points.length ? sum("storage_charge_kwh") : null) }} /
              {{
                fmt(points.length ? sum("storage_discharge_kwh") : null)
              }}
              kWh</b
            ></span
          >
        </div>
      </section>
      <section class="visual-panel right-middle">
        <h2>光伏与风电趋势</h2>
        <BaseChart
          :option="generationOption"
          :empty="!points.length"
          height="190px"
        />
      </section>
      <DeviceMonitorPanel
        :devices="devices"
        :site-id="siteId"
        :anomaly-count="overview?.anomaly_count"
        @device="chooseDevice"
        @anomalies="router.push('/data')"
      />
      <aside v-if="selected" class="object-drawer">
        <button class="drawer-close" @click="selected = null">×</button
        ><span>对象详情</span>
        <h2>{{ selected.name }}</h2>
        <p>
          类型：{{
            "building_type" in selected
              ? typeName(selected.building_type)
              : typeName(selected.device_type)
          }}
        </p>
        <p>
          状态：{{ selected.status === "ACTIVE" ? "运行中" : selected.status }}
        </p>
        <template v-if="'building_type' in selected"
          ><p>
            建筑编码：{{ selected.metadata_json?.building_id || selected.code }}
          </p>
          <p>
            {{ liveSnapshot ? "本年累计用电：" : "年用电："
            }}{{
              fmt(Number(selected.metadata_json?.annual_energy_kwh ?? 0))
            }}
            千瓦时
          </p>
          <p>
            {{ liveSnapshot ? "本年累计用水：" : "年用水："
            }}{{
              fmt(Number(selected.metadata_json?.annual_water_m3 ?? 0))
            }}
            立方米
          </p>
          <p>
            {{ liveSnapshot ? "本年累计碳排：" : "年碳排："
            }}{{
              fmt(Number(selected.metadata_json?.annual_emission_tco2e ?? 0))
            }}
            吨二氧化碳当量
          </p>
          <p>
            数据性质：{{ selected.metadata_json?.data_notice || "未标注" }}
          </p></template
        ><BaseChart
          v-if="telemetry?.data.length"
          :option="telemetryOption"
          height="190px"
        />
        <p v-else-if="!('building_type' in selected)" class="no-data">
          暂无该对象遥测数据
        </p>
        <button
          class="analysis-link"
          @click="
            router.push({
              path: '/carbon',
              query: {
                site: siteId,
                building: 'building_type' in selected ? selected.id : undefined,
                at: liveSnapshot?.timestamp,
              },
            })
          "
        >
          查看碳核算</button
        ><button
          class="analysis-link"
          @click="router.push('/carbon-neutral-simulation')"
        >
          进入碳中和仿真
        </button>
      </aside>
    </div>
    <div v-else class="screen-message">
      <b>暂无园区</b
      ><button @click="router.push('/park?create=site')">前往园区管理</button>
    </div>
  </main>
</template>
