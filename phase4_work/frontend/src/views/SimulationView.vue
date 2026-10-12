<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { EChartsOption } from "echarts";
import { simulationApi } from "@/api/simulation";
import {http} from '@/api/http';
import { scenariosApi } from "@/api/scenarios";
import { useSiteStore } from "@/stores/site";
import PageHeader from "@/components/PageHeader.vue";
import StatCard from "@/components/StatCard.vue";
import BaseChart from "@/components/BaseChart.vue";
import LoadingState from "@/components/LoadingState.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import StatusTag from "@/components/StatusTag.vue";
import MeasureCard from "@/components/MeasureCard.vue";
import type {
  AnnualSimulationResult,
  EVChargerConfig,
  GreenPowerConfig,
  HourlySimulationResult,
  HVACConfig,
  LightingConfig,
  LongTermPathRun,
  MeasureType,
  PVConfig,
  QualitySummary,
  Scenario,
  ScenarioMeasure,
  ScenarioVersion,
  SimulationTask,
  StorageConfig,
  StrengthenedPathRequest,
  WeatherSite,
  WindConfig,
} from "@/types";

const route = useRoute(),
  router = useRouter(),
  siteStore = useSiteStore();
const loading = ref(true),
  contextLoading = ref(false),
  running = ref(false),
  error = ref<string | null>(null),
  failure = ref<string | null>(null),
  confirmVisible = ref(false);
const scenarios = ref<Scenario[]>([]),
  versions = ref<ScenarioVersion[]>([]),
  weatherSites = ref<WeatherSite[]>([]),
  scenarioId = ref<number | null>(null),
  versionId = ref<number | null>(null),
  weatherSiteId = ref<number | null>(null),
  mode = ref<"HOURLY" | "ANNUAL">("HOURLY"),
  year = ref(new Date().getFullYear()),
  timezone = ref("Asia/Shanghai"),
  dates = ref<[Date, Date]>([
    new Date(year.value, 0, 1),
    new Date(year.value + 1, 0, 1),
  ]);
const electricityPrice = ref(0.57),
  feedInTariff = ref(0.42),
  loadQuality = ref<QualitySummary | null>(null),
  weatherQuality = ref<QualitySummary | null>(null),
  dynamicPrices = ref(0),
  dynamicFactors = ref(0),
  models = ref<string[]>([]);
const hourly = ref<HourlySimulationResult | null>(null),
  annual = ref<AnnualSimulationResult | null>(null);
const taskMeta = ref<SimulationTask | null>(null);
const longTerm = ref<LongTermPathRun | null>(null),
  longTermRunning = ref(false);
const strengthened = ref<LongTermPathRun | null>(null),
  strengthenRunning = ref(false);
const longTermForm = reactive({
  start_year: 2024,
  end_year: 2060,
  target_peak_year: 2030,
  target_neutral_year: 2060,
  annual_load_growth_rate: 0.01,
  comprehensive_energy_target_rate: 0.15,
  carbon_quota_t: 2200,
  annual_quota_change_rate: 0,
  annual_grid_factor_change_rate: -0.015,
  annual_price_change_rate: 0.02,
  carbon_price_per_t: 85,
  neutrality_threshold_t: 1,
});
const strengthenForm = reactive<StrengthenedPathRequest>({
  pv_annual_addition_kw: 30,
  wind_annual_addition_kw: 0,
  storage_expansion_year: 2035,
  storage_expansion_kwh: 300,
  additional_hvac_saving_rate: 0.05,
  additional_lighting_saving_rate: 0.05,
  green_power_ratio: 0.8,
  annual_ccer_t: 300,
  annual_grid_factor_change_rate: -0.02,
});
const enabled = reactive<Record<MeasureType, boolean>>({
  PV: false,
  WIND: false,
  STORAGE: false,
  HVAC: false,
  LIGHTING: false,
  EV_CHARGER: false,
  GREEN_POWER: false,
});
const selectedMeasure = ref<MeasureType>("PV");
const measureNames: Record<MeasureType, string> = {
  PV: "光伏（PV）",
  WIND: "风电（WIND）",
  STORAGE: "储能（STORAGE）",
  HVAC: "空调节能",
  LIGHTING: "照明节能",
  EV_CHARGER: "充电桩（EV Charger）",
  GREEN_POWER: "绿电",
};
const years = reactive<
  Record<MeasureType, { start: number; end: number | null }>
>({
  PV: { start: year.value, end: null },
  WIND: { start: year.value, end: null },
  STORAGE: { start: year.value, end: null },
  HVAC: { start: year.value, end: null },
  LIGHTING: { start: year.value, end: null },
  EV_CHARGER: { start: year.value, end: null },
  GREEN_POWER: { start: year.value, end: null },
});
const pv = reactive<PVConfig>({
  capacity_kw: 100,
  tilt_deg: 30,
  azimuth_deg: 180,
  inverter_efficiency: 0.96,
  irradiance_mode: "GHI",
  noct_c: 45,
  temperature_coefficient_per_c: -0.004,
  performance_ratio: 0.8,
});
const wind = reactive<WindConfig>({
  rated_power_kw: 100,
  cut_in_speed_m_s: 3,
  rated_speed_m_s: 10,
  cut_out_speed_m_s: 25,
  power_curve: [],
});
const storage = reactive<StorageConfig>({
  capacity_kwh: 200,
  max_charge_kw: 50,
  max_discharge_kw: 50,
  charge_efficiency: 0.95,
  discharge_efficiency: 0.95,
  soc_initial: 0.5,
  soc_min: 0.1,
  soc_max: 0.9,
  strategy: "PV_SELF_CONSUMPTION",
});
const hvac = reactive<HVACConfig>({ saving_rate: 0.1, load_share: 1 }),
  lighting = reactive<LightingConfig>({ saving_rate: 0.1, load_share: 1 });
const ev = reactive<EVChargerConfig>({
  charger_count: 10,
  rated_power_kw_per_charger: 7,
  utilization_rate: 0.5,
  daily_energy_kwh: 100,
  charging_start_hour: 8,
  charging_end_hour: 20,
  arrival_hour: 18,
  departure_hour: 7,
});
const green = reactive<GreenPowerConfig>({
  purchase_share: 0.2,
  purchase_kwh: 0,
  emission_factor_kg_per_kwh: 0,
  premium_per_kwh: 0.05,
});
const configMap: Record<MeasureType, Record<string, unknown>> = {
  PV: pv as unknown as Record<string, unknown>,
  WIND: wind as unknown as Record<string, unknown>,
  STORAGE: storage as unknown as Record<string, unknown>,
  HVAC: hvac as unknown as Record<string, unknown>,
  LIGHTING: lighting as unknown as Record<string, unknown>,
  EV_CHARGER: ev as unknown as Record<string, unknown>,
  GREEN_POWER: green as unknown as Record<string, unknown>,
};
function resetMeasure(type: MeasureType) {
  const defaults: Record<MeasureType, Record<string, unknown>> = {
    PV: {
      capacity_kw: 100,
      tilt_deg: 30,
      azimuth_deg: 180,
      inverter_efficiency: 0.96,
      irradiance_mode: "GHI",
      noct_c: 45,
      temperature_coefficient_per_c: -0.004,
      performance_ratio: 0.8,
    },
    WIND: {
      rated_power_kw: 100,
      cut_in_speed_m_s: 3,
      rated_speed_m_s: 10,
      cut_out_speed_m_s: 25,
      power_curve: [],
    },
    STORAGE: {
      capacity_kwh: 200,
      max_charge_kw: 50,
      max_discharge_kw: 50,
      charge_efficiency: 0.95,
      discharge_efficiency: 0.95,
      soc_initial: 0.5,
      soc_min: 0.1,
      soc_max: 0.9,
      strategy: "PV_SELF_CONSUMPTION",
    },
    HVAC: { saving_rate: 0.1, load_share: 1 },
    LIGHTING: { saving_rate: 0.1, load_share: 1 },
    EV_CHARGER: {
      charger_count: 10,
      rated_power_kw_per_charger: 7,
      utilization_rate: 0.5,
      daily_energy_kwh: 100,
      charging_start_hour: 8,
      charging_end_hour: 20,
      arrival_hour: 18,
      departure_hour: 7,
    },
    GREEN_POWER: {
      purchase_share: 0.2,
      purchase_kwh: 0,
      emission_factor_kg_per_kwh: 0,
      premium_per_kwh: 0.05,
    },
  };
  Object.assign(configMap[type], defaults[type]);
}
const selectedScenario = computed(
    () => scenarios.value.find((x) => x.id === scenarioId.value) || null,
  ),
  selectedVersion = computed(
    () => versions.value.find((x) => x.id === versionId.value) || null,
  );
const temporary = computed(
    () => mode.value === "HOURLY" && Boolean(selectedVersion.value),
  ),
  rangeStart = computed(() => dates.value[0].toISOString()),
  rangeEnd = computed(() => dates.value[1].toISOString());
const measurePayload = computed<ScenarioMeasure[]>(() =>
  Object.keys(enabled)
    .filter((x) => enabled[x as MeasureType])
    .map((type) => ({
      measure_type: type as MeasureType,
      start_year: years[type as MeasureType].start,
      end_year: years[type as MeasureType].end,
      parameters_json: { ...configMap[type as MeasureType] },
    })),
);
const maxBalanceError = computed(() =>
  hourly.value?.results.length
    ? Math.max(
        ...hourly.value.results.map((x) =>
          Math.abs(x.energy_balance_error_kwh),
        ),
      )
    : null,
);
const renewableShare = computed(() =>
  hourly.value && hourly.value.summary.load_base_kwh
    ? hourly.value.summary.renewable_generation_kwh /
      hourly.value.summary.load_base_kwh
    : null,
);
const longTermOption = computed<EChartsOption>(() => {
  const rows = longTerm.value?.result_snapshot_json.annual || [];
  const result = longTerm.value?.result_snapshot_json;
  const milestoneData = (result?.key_milestones || []).map((x) => ({
    name:
      x.measures.map((m) => measureNames[m as MeasureType] || m).join("、") +
      "投产",
    xAxis: x.year,
  }));
  return {
    tooltip: { trigger: "axis" },
    legend: { data: ["年度净碳排放", "年度碳配额"] },
    grid: { left: 70, right: 30, top: 60, bottom: 45 },
    xAxis: { type: "category", data: rows.map((x) => x.year) },
    yAxis: { type: "value", name: "吨二氧化碳当量" },
    series: [
      {
        name: "年度净碳排放",
        type: "line",
        smooth: true,
        data: rows.map((x) => Number(x.net_emission_t.toFixed(2))),
        markPoint: {
          data: [
            ...(result
              ? [
                  {
                    name: "实际达峰年",
                    coord: [result.actual_peak_year, result.peak_emission_t],
                    value: result.actual_peak_year,
                  },
                ]
              : []),
            ...(result?.actual_neutral_year
              ? [
                  {
                    name: "实际中和年",
                    coord: [result.actual_neutral_year, 0],
                    value: result.actual_neutral_year,
                  },
                ]
              : []),
          ],
        },
        markLine: {
          data: [
            { name: "目标达峰年", xAxis: longTermForm.target_peak_year },
            { name: "基准年", xAxis: longTermForm.start_year },
            ...milestoneData,
          ],
        },
      },
      {
        name: "年度碳配额",
        type: "line",
        lineStyle: { type: "dashed" },
        data: rows.map((x) => Number(x.carbon_quota_t.toFixed(2))),
      },
    ],
  };
});
async function runLongTerm() {
  if (!versionId.value) {
    failure.value = "请选择正式场景版本后再执行长期推演";
    return;
  }
  longTermRunning.value = true;
  failure.value = null;
  try {
    longTerm.value = await simulationApi.runLongTerm({
      site_id: siteStore.currentSite?.id,
      scenario_version_id: versionId.value,
      baseline_task_id: taskId.value || undefined,
      ...longTermForm,
      electricity_price_per_kwh: electricityPrice.value,
      measures: measurePayload.value,
    });
  } catch (e) {
    failure.value = (e as { message?: string }).message || "长期路径推演失败";
  } finally {
    longTermRunning.value = false;
  }
}
async function runStrengthened() {
  if (!longTerm.value) return;
  strengthenRunning.value = true;
  failure.value = null;
  try {
    strengthened.value = await simulationApi.strengthenLongTerm(
      longTerm.value.id,
      { ...strengthenForm },
    );
  } catch (e) {
    failure.value = (e as { message?: string }).message || "强化方案推演失败";
  } finally {
    strengthenRunning.value = false;
  }
}
const netCost = computed(() =>
  hourly.value
    ? hourly.value.summary.electricity_cost -
      hourly.value.summary.feed_in_revenue
    : null,
);
const taskId = computed(
    () => hourly.value?.summary.task_id || annual.value?.task.id || null,
  ),
  taskStatus = computed(() =>
    hourly.value ? "SUCCESS" : annual.value?.task.status || null,
  );
const validationErrors = computed(() => {
  const e: string[] = [];
  for (const [type, cfg] of Object.entries(configMap)) {
    if (!enabled[type as MeasureType]) continue;
    for (const [key, value] of Object.entries(cfg))
      if (
        typeof value === "number" &&
        value < 0 &&
        !["temperature_coefficient_per_c"].includes(key)
      )
        e.push(`${type}：${key} 不能为负`);
    const timing = years[type as MeasureType];
    if (timing.end !== null && timing.end < timing.start)
      e.push(`${type}：结束年份不得早于启用年份`);
  }
  if (
    enabled.PV &&
    !(pv.inverter_efficiency >= 0 && pv.inverter_efficiency <= 1)
  )
    e.push("PV：逆变器效率必须为 0~1");
  if (
    enabled.WIND &&
    !(
      wind.cut_in_speed_m_s < wind.rated_speed_m_s &&
      wind.rated_speed_m_s < wind.cut_out_speed_m_s
    )
  )
    e.push("WIND：必须满足切入风速 < 额定风速 < 切出风速");
  if (
    enabled.WIND &&
    wind.power_curve?.some((x) => x.power_fraction < 0 || x.power_fraction > 1)
  )
    e.push("WIND：功率曲线比例必须为 0~1");
  if (enabled.STORAGE) {
    if (
      ![storage.charge_efficiency, storage.discharge_efficiency].every(
        (x) => x >= 0 && x <= 1,
      )
    )
      e.push("STORAGE：充放电效率必须为 0~1");
    if (!(
      storage.soc_min <= storage.soc_initial &&
      storage.soc_initial <= storage.soc_max
    ))
      e.push("STORAGE：必须满足最小 SOC ≤ 初始 SOC ≤ 最大 SOC");
  }
  if (enabled.HVAC && (hvac.saving_rate < 0 || hvac.saving_rate > 1))
    e.push("HVAC：节能比例必须为 0~1");
  if (
    enabled.LIGHTING &&
    (lighting.saving_rate < 0 || lighting.saving_rate > 1)
  )
    e.push("LIGHTING：节能比例必须为 0~1");
  if (
    enabled.EV_CHARGER &&
    (ev.utilization_rate < 0 || ev.utilization_rate > 1)
  )
    e.push("EV：利用率必须为 0~1");
  if (
    enabled.GREEN_POWER &&
    (green.purchase_share < 0 || green.purchase_share > 1)
  )
    e.push("GREEN_POWER：绿电比例必须为 0~1");
  return e;
});
const measureSummary = (type: MeasureType) =>
  ({
    PV: `${pv.capacity_kw} kW · ${pv.irradiance_mode}`,
    WIND: `${wind.rated_power_kw} kW · ${wind.cut_in_speed_m_s}/${wind.rated_speed_m_s}/${wind.cut_out_speed_m_s} m/s`,
    STORAGE: `${storage.capacity_kwh} kWh · ${storage.strategy}`,
    HVAC: `节能 ${(hvac.saving_rate * 100).toFixed(0)}%`,
    LIGHTING: `节能 ${(lighting.saving_rate * 100).toFixed(0)}%`,
    EV_CHARGER: `${ev.charger_count} 枪 · ${ev.daily_energy_kwh} kWh/日`,
    GREEN_POWER: `比例 ${(green.purchase_share * 100).toFixed(0)}% · 仅碳属性/经济性`,
  })[type];
const xaxis = computed(
  () =>
    hourly.value?.results.map((x) =>
      new Date(x.timestamp).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
      }),
    ) || [],
);
function lineOption(
  series: {
    name: string;
    key: keyof HourlySimulationResult["results"][number];
  }[],
  cumulative = false,
): EChartsOption {
  return {
    grid: { left: 64, right: 25, top: 52, bottom: 40 },
    dataZoom: [{ type: "inside" }, { type: "slider", height: 16 }],
    xAxis: { type: "category", data: xaxis.value },
    yAxis: { type: "value" },
    series: series.map((s) => {
      let sum = 0;
      return {
        name: s.name,
        type: "line",
        showSymbol: false,
        data: (hourly.value?.results || []).map((row) => {
          const v = Number(row[s.key]);
          sum += v;
          return cumulative ? sum : v;
        }),
      };
    }),
  };
}
const energyOption = computed(() =>
    lineOption([
      { name: "原始负荷", key: "load_base_kwh" },
      { name: "节能后负荷", key: "load_after_saving_kwh" },
      { name: "充电桩", key: "ev_charging_load_kwh" },
      { name: "可再生能源", key: "renewable_generation_kwh" },
    ]),
  ),
  gridOption = computed(() =>
    lineOption([
      { name: "电网购电", key: "grid_power_kwh" },
      { name: "上网", key: "renewable_export_kwh" },
    ]),
  ),
  generationOption = computed(() =>
    lineOption([
      { name: "PV", key: "pv_generation_kwh" },
      { name: "风电", key: "wind_generation_kwh" },
    ]),
  ),
  socOption = computed(() =>
    lineOption([{ name: "SOC", key: "storage_soc_kwh" }]),
  ),
  storageOption = computed(() =>
    lineOption([
      { name: "充电", key: "storage_charge_kwh" },
      { name: "放电", key: "storage_discharge_kwh" },
    ]),
  ),
  carbonOption = computed(() =>
    lineOption([
      { name: "小时碳排", key: "carbon_emission_t" },
      { name: "绿电减排", key: "green_power_carbon_reduction_t" },
    ]),
  ),
  cumulativeCarbonOption = computed(() =>
    lineOption([{ name: "累计碳排", key: "carbon_emission_t" }], true),
  ),
  costOption = computed(() =>
    lineOption(
      [
        { name: "累计购电成本", key: "electricity_cost" },
        { name: "累计上网收益", key: "feed_in_revenue" },
      ],
      true,
    ),
  );

async function initialize() {
  loading.value = true;
  error.value = null;
  try {
    await siteStore.loadSites();
    const requestedSite = Number(route.query.site);
    if (requestedSite) {
      const s = siteStore.sites.find((x) => x.id === requestedSite);
      if (s) siteStore.selectSite(s);
    }
    const requestedVersion = Number(route.query.scenario_version);
    await loadContext(requestedVersion || undefined);
    models.value = (await simulationApi.models()).models;
  } catch (e) {
    error.value = (e as { message?: string }).message || "仿真配置加载失败";
  } finally {
    loading.value = false;
  }
}
async function loadContext(requestedVersion?: number) {
  const site = siteStore.currentSite;
  if (!site) {
    scenarios.value = [];
    return;
  }
  contextLoading.value = true;
  try {
    timezone.value = site.timezone;
    [scenarios.value, weatherSites.value] = await Promise.all([
      simulationApi.scenarios(site.enterprise_id),
      simulationApi.weatherSites(site.enterprise_id),
    ]);
    if (requestedVersion) {
      for (const s of scenarios.value) {
        const list = await scenariosApi.versions(s.id);
        const found = list.find((v) => v.id === requestedVersion);
        if (found) {
          scenarioId.value = s.id;
          versions.value = list;
          versionId.value = found.id;
          applySnapshot(found);
          break;
        }
      }
    }
    if (!scenarioId.value && scenarios.value.length) {
      scenarioId.value = scenarios.value[0].id;
      await loadVersions();
    }
    weatherSiteId.value = weatherSites.value[0]?.id || null;
    await loadAvailability();
  } finally {
    contextLoading.value = false;
  }
}
async function loadVersions() {
  if (!scenarioId.value) return;
  versions.value = await scenariosApi.versions(scenarioId.value);
  versionId.value =
    selectedScenario.value?.current_version_id ||
    versions.value.at(-1)?.id ||
    null;
  if (selectedVersion.value) applySnapshot(selectedVersion.value);
  await loadAvailability();
}
function applySnapshot(version: ScenarioVersion) {
  const snap = version.parameter_snapshot_json,
    base = Number(snap.base_year || snap.start_year);
  if (base) {
    year.value = base;
    dates.value = [new Date(base, 0, 1), new Date(base + 1, 0, 1)];
  }
  for (const key of Object.keys(enabled) as MeasureType[]) enabled[key] = false;
  const list = Array.isArray(snap.measures)
    ? (snap.measures as {
        measure_type: MeasureType;
        start_year: number;
        end_year?: number | null;
        parameters_json: Record<string, unknown>;
      }[])
    : [];
  for (const item of list) {
    if (!configMap[item.measure_type]) continue;
    enabled[item.measure_type] = true;
    years[item.measure_type] = {
      start: item.start_year,
      end: item.end_year || null,
    };
    Object.assign(configMap[item.measure_type], item.parameters_json);
  }
}
async function loadAvailability() {
  const site = siteStore.currentSite;
  if (!site) return;
  if(site.code==='HBUE'){
    const data=await http.get(`/api/result-interface/campuses/${site.id}/simulation-baseline`,{params:{year:year.value}}) as unknown as {load:QualitySummary;weather:QualitySummary};
    loadQuality.value=data.load;weatherQuality.value=data.weather;dynamicPrices.value=0;dynamicFactors.value=0;return;
  }
  const requests: Promise<unknown>[] = [
    simulationApi
      .loadQuality(
        site.enterprise_id,
        rangeStart.value,
        rangeEnd.value,
        timezone.value,
      )
      .then((x) => (loadQuality.value = x))
      .catch(() => (loadQuality.value = null)),
  ];
  if (weatherSiteId.value)
    requests.push(
      simulationApi
        .weatherQuality(
          weatherSiteId.value,
          rangeStart.value,
          rangeEnd.value,
          timezone.value,
        )
        .then((x) => (weatherQuality.value = x))
        .catch(() => (weatherQuality.value = null)),
    );
  const enterprise = await simulationApi.enterprise(site.enterprise_id);
  requests.push(
    simulationApi
      .prices(site.enterprise_id, rangeStart.value, rangeEnd.value)
      .then((x) => (dynamicPrices.value = x.length))
      .catch(() => (dynamicPrices.value = 0)),
  );
  if (enterprise.region)
    requests.push(
      simulationApi
        .factors(enterprise.region, rangeStart.value, rangeEnd.value)
        .then((x) => (dynamicFactors.value = x.length))
        .catch(() => (dynamicFactors.value = 0)),
    );
  await Promise.all(requests);
}
async function submit() {
  confirmVisible.value = false;
  failure.value = null;
  running.value = true;
  hourly.value = null;
  annual.value = null;
  taskMeta.value = null;
  try {
    if (!scenarioId.value) throw new Error("请选择场景");
    if (validationErrors.value.length)
      throw new Error(validationErrors.value.join("；"));
    if (mode.value === "HOURLY") {
      hourly.value = await simulationApi.runHourly({
        site_id: siteStore.currentSite?.id,
        scenario_id: scenarioId.value,
        scenario_version_id: versionId.value || undefined,
        year: year.value,
        start_time: rangeStart.value,
        end_time: rangeEnd.value,
        electricity_price_per_kwh: electricityPrice.value,
        feed_in_tariff_per_kwh: feedInTariff.value,
        store_hourly_results: true,
        weather_site_id: weatherSiteId.value || undefined,
        temporary_measures: measurePayload.value.map(
          ({ measure_type, start_year, end_year, parameters_json }) => ({
            measure_type,
            start_year,
            end_year,
            parameters_json,
          }),
        ),
      });
      taskMeta.value = (
        await simulationApi.getHourly(hourly.value.summary.task_id)
      ).task;
    } else
      annual.value = await simulationApi.runAnnual({
        site_id: siteStore.currentSite?.id,
        scenario_id: scenarioId.value,
        scenario_version_id: versionId.value || undefined,
        electricity_price_per_kwh: electricityPrice.value,
        feed_in_tariff_per_kwh: feedInTariff.value,
      });
  } catch (e) {
    failure.value = (e as { message?: string }).message || "仿真执行失败";
  } finally {
    running.value = false;
  }
}
onMounted(initialize);
</script>

<template>
  <section>
    <PageHeader
      kicker="SIMULATION WORKBENCH"
      title="碳中和仿真工作台"
      description="配置负荷、气象、七类措施与市场参数，调用既有年度/小时仿真引擎。"
      ><el-button :loading="loading" @click="initialize"
        ><el-icon><Refresh /></el-icon>刷新</el-button
      ></PageHeader
    >
    <LoadingState v-if="loading" /><ErrorState
      v-else-if="error"
      :message="error"
      @retry="initialize"
    /><template v-else-if="siteStore.currentSite">
      <div class="business-context">
        <span
          >当前园区/站点：<b>{{ siteStore.currentSite.name }}</b></span
        ><span
          >当前场景版本：<b>{{
            selectedVersion
              ? `V${selectedVersion.version_number} · #${selectedVersion.id}`
              : "未选择"
          }}</b></span
        ><span
          >当前仿真任务：<b>{{ taskId ? `#${taskId}` : "尚未创建" }}</b></span
        ><span
          >数据时间范围：<b
            >{{ dates[0].toLocaleDateString("zh-CN") }} —
            {{ dates[1].toLocaleDateString("zh-CN") }}</b
          ></span
        ><el-button
          @click="
            router.push({
              path: '/recommendations',
              query: { site: siteStore.currentSite.id },
            })
          "
          >智能推荐</el-button
        ><el-button @click="router.push('/scenarios')">场景比较</el-button
        ><el-tooltip
          :disabled="Boolean(taskId && versionId)"
          content="请先完成仿真并取得任务"
          ><span
            ><el-button
              :disabled="!taskId || !versionId"
              @click="
                router.push({
                  path: '/reports',
                  query: { scenario_version: versionId, task: taskId },
                })
              "
              >生成报告</el-button
            ></span
          ></el-tooltip
        >
      </div>
      <el-steps
        :active="hourly || annual ? 3 : scenarioId ? 1 : 0"
        finish-status="success"
        simple
        class="simulation-steps"
        ><el-step title="基础配置" /><el-step title="数据与措施" /><el-step
          title="确认提交" /><el-step title="查看结果"
      /></el-steps>
      <article class="panel simulation-section">
        <div class="panel-head">
          <div>
            <span>BASIC CONFIGURATION</span>
            <h2>基础配置</h2>
          </div>
          <el-tag v-if="temporary" type="warning"
            >当前为临时仿真配置，不修改历史场景版本</el-tag
          >
        </div>
        <div class="simulation-form-grid">
          <el-form-item label="园区/站点"
            ><el-select
              :model-value="siteStore.currentSite.id"
              @change="
                (id: number) => {
                  siteStore.selectSite(
                    siteStore.sites.find((x) => x.id === id) || null,
                  );
                  router.replace({ query: { site: id } });
                  loadContext();
                }
              "
              ><el-option
                v-for="s in siteStore.sites"
                :key="s.id"
                :label="s.name"
                :value="s.id" /></el-select></el-form-item
          ><el-form-item label="场景"
            ><el-select v-model="scenarioId" @change="loadVersions"
              ><el-option
                v-for="s in scenarios"
                :key="s.id"
                :label="s.name"
                :value="s.id" /></el-select></el-form-item
          ><el-form-item label="不可变版本"
            ><el-select
              v-model="versionId"
              @change="selectedVersion && applySnapshot(selectedVersion)"
              ><el-option
                v-for="v in versions"
                :key="v.id"
                :label="`V${v.version_number} · ${v.scenario_type}`"
                :value="v.id" /></el-select></el-form-item
          ><el-form-item label="仿真模式"
            ><el-radio-group v-model="mode"
              ><el-radio-button value="HOURLY">小时级</el-radio-button
              ><el-radio-button value="ANNUAL"
                >年度</el-radio-button
              ></el-radio-group
            ></el-form-item
          ><el-form-item label="仿真年份"
            ><el-input-number
              v-model="year"
              :min="1900"
              :max="2200" /></el-form-item
          ><el-form-item label="时区"
            ><el-input v-model="timezone" /></el-form-item
          ><el-form-item label="数据起止" class="span-two"
            ><el-date-picker v-model="dates" type="datetimerange"
          /></el-form-item>
        </div>
      </article>

      <article class="panel simulation-section">
        <div class="panel-head">
          <div>
            <span>LOAD & WEATHER</span>
            <h2>负荷与气象</h2>
          </div>
        </div>
        <div class="availability-grid">
          <div>
            <span>小时负荷</span
            ><strong>{{
              loadQuality
                ? `${loadQuality.observed_points}/${loadQuality.expected_points} 点`
                : "暂无数据"
            }}</strong
            ><el-progress
              v-if="loadQuality"
              :percentage="loadQuality.completeness_rate * 100"
            /><el-alert
              v-if="loadQuality && loadQuality.completeness_rate < 1"
              title="当前时间范围数据不完整"
              type="warning"
              :closable="false"
            />
          </div>
          <div>
            <span>气象站点</span
            ><el-select
              v-model="weatherSiteId"
              clearable
              @change="loadAvailability"
              ><el-option
                v-for="s in weatherSites"
                :key="s.id"
                :label="`${s.name} · ${s.timezone}`"
                :value="s.id" /></el-select
            ><strong>{{
              weatherQuality
                ? `${weatherQuality.observed_points}/${weatherQuality.expected_points} 点 · ${(weatherQuality.completeness_rate * 100).toFixed(1)}%`
                : "暂无气象数据"
            }}</strong
            ><el-alert
              v-if="weatherQuality && weatherQuality.completeness_rate < 1"
              title="当前时间范围数据不完整"
              type="warning"
              :closable="false"
            />
          </div>
          <div>
            <span>数据范围</span
            ><strong
              >{{ dates[0].toLocaleDateString() }} —
              {{ dates[1].toLocaleDateString() }}</strong
            ><small>最近检查：{{ new Date().toLocaleString("zh-CN") }}</small>
          </div>
        </div>
      </article>

      <section class="simulation-section">
        <div class="section-heading">
          <span>LOW-CARBON MEASURES</span>
          <h2>低碳措施</h2>
          <p>统一启用、校验、摘要和临时配置流程。</p>
        </div>
        <div v-if="measurePayload.length" class="measure-years">
          <div v-for="item in measurePayload" :key="item.measure_type">
            <b>{{ item.measure_type }}</b
            ><label
              >启用年份
              <el-input-number
                v-model="years[item.measure_type].start" /></label
            ><label
              >结束年份
              <el-input-number v-model="years[item.measure_type].end" clearable
            /></label>
          </div>
        </div>
        <div class="measure-workbench">
          <aside class="measure-selector">
            <button
              v-for="(name, type) in measureNames"
              :key="type"
              :class="{ active: selectedMeasure === type }"
              @click="selectedMeasure = type"
            >
              <el-checkbox
                :model-value="enabled[type]"
                @click.stop
                @change="enabled[type] = $event"
              />{{ name }}
            </button>
          </aside>
          <main>
            <div class="measure-toolbar">
              <b>{{ measureNames[selectedMeasure] }}参数</b
              ><el-button @click="resetMeasure(selectedMeasure)"
                >恢复默认</el-button
              >
            </div>
            <div class="measure-grid">
              <MeasureCard
                v-show="selectedMeasure === 'PV'"
                title="光伏"
                code="PV"
                :enabled="enabled.PV"
                :summary="measureSummary('PV')"
                @toggle="enabled.PV = $event"
                ><div class="mini-form">
                  <label
                    >装机 kW<el-input-number
                      v-model="pv.capacity_kw"
                      :min="0" /></label
                  ><label>倾角°<el-input-number v-model="pv.tilt_deg" /></label
                  ><label
                    >方位角°<el-input-number v-model="pv.azimuth_deg" /></label
                  ><label
                    >逆变器效率<el-input-number
                      v-model="pv.inverter_efficiency"
                      :step="0.01" /></label
                  ><label
                    >辐照模式<el-select v-model="pv.irradiance_mode"
                      ><el-option label="GHI" value="GHI" /><el-option
                        label="POA"
                        value="POA" /></el-select></label
                  ><label>NOCT °C<el-input-number v-model="pv.noct_c" /></label
                  ><label
                    >温度系数<el-input-number
                      v-model="pv.temperature_coefficient_per_c"
                      :step="0.001" /></label
                  ><label
                    >上网出力限制 kW<el-input-number
                      v-model="pv.export_limit_kw"
                      :min="0"
                  /></label></div
              ></MeasureCard>
              <MeasureCard
                v-show="selectedMeasure === 'WIND'"
                title="风电"
                code="WIND"
                :enabled="enabled.WIND"
                :summary="measureSummary('WIND')"
                @toggle="enabled.WIND = $event"
                ><div class="mini-form">
                  <label
                    >额定功率 kW<el-input-number
                      v-model="wind.rated_power_kw" /></label
                  ><label
                    >切入 m/s<el-input-number
                      v-model="wind.cut_in_speed_m_s" /></label
                  ><label
                    >额定 m/s<el-input-number
                      v-model="wind.rated_speed_m_s" /></label
                  ><label
                    >切出 m/s<el-input-number v-model="wind.cut_out_speed_m_s"
                  /></label>
                </div>
                <div class="curve-editor">
                  <b>自定义功率曲线</b>
                  <div v-for="(p, i) in wind.power_curve" :key="i">
                    <el-input-number v-model="p.wind_speed_m_s" /><span
                      >m/s →</span
                    ><el-input-number
                      v-model="p.power_fraction"
                      :step="0.1"
                    /><el-button
                      link
                      type="danger"
                      @click="wind.power_curve?.splice(i, 1)"
                      >删除</el-button
                    >
                  </div>
                  <el-button
                    link
                    @click="
                      wind.power_curve?.push({
                        wind_speed_m_s: 0,
                        power_fraction: 0,
                      })
                    "
                    >+ 添加曲线点</el-button
                  >
                </div></MeasureCard
              >
              <MeasureCard
                v-show="selectedMeasure === 'STORAGE'"
                title="储能"
                code="STORAGE"
                :enabled="enabled.STORAGE"
                :summary="measureSummary('STORAGE')"
                @toggle="enabled.STORAGE = $event"
                ><div class="mini-form">
                  <label
                    >容量 kWh<el-input-number
                      v-model="storage.capacity_kwh" /></label
                  ><label
                    >最大充电 kW<el-input-number
                      v-model="storage.max_charge_kw" /></label
                  ><label
                    >最大放电 kW<el-input-number
                      v-model="storage.max_discharge_kw" /></label
                  ><label
                    >充电效率<el-input-number
                      v-model="storage.charge_efficiency"
                      :step="0.01" /></label
                  ><label
                    >放电效率<el-input-number
                      v-model="storage.discharge_efficiency"
                      :step="0.01" /></label
                  ><label
                    >初始 SOC<el-input-number
                      v-model="storage.soc_initial"
                      :step="0.1" /></label
                  ><label
                    >最小 SOC<el-input-number
                      v-model="storage.soc_min"
                      :step="0.1" /></label
                  ><label
                    >最大 SOC<el-input-number
                      v-model="storage.soc_max"
                      :step="0.1" /></label
                  ><label
                    >策略<el-select v-model="storage.strategy"
                      ><el-option
                        label="光伏自用"
                        value="PV_SELF_CONSUMPTION" /><el-option
                        label="峰谷套利"
                        value="PEAK_VALLEY_ARBITRAGE" /></el-select
                  ></label></div
              ></MeasureCard>
              <MeasureCard
                v-show="selectedMeasure === 'HVAC'"
                title="空调节能"
                code="HVAC"
                :enabled="enabled.HVAC"
                :summary="measureSummary('HVAC')"
                @toggle="enabled.HVAC = $event"
                ><div class="mini-form">
                  <label
                    >节能比例<el-input-number
                      v-model="hvac.saving_rate"
                      :step="0.05"
                  /></label></div
              ></MeasureCard>
              <MeasureCard
                v-show="selectedMeasure === 'LIGHTING'"
                title="照明节能"
                code="LIGHTING"
                :enabled="enabled.LIGHTING"
                :summary="measureSummary('LIGHTING')"
                @toggle="enabled.LIGHTING = $event"
                ><div class="mini-form">
                  <label
                    >节能比例<el-input-number
                      v-model="lighting.saving_rate"
                      :step="0.05"
                  /></label></div
              ></MeasureCard>
              <MeasureCard
                v-show="selectedMeasure === 'EV_CHARGER'"
                title="充电桩"
                code="EV_CHARGER"
                :enabled="enabled.EV_CHARGER"
                :summary="measureSummary('EV_CHARGER')"
                @toggle="enabled.EV_CHARGER = $event"
                ><div class="mini-form">
                  <label
                    >数量<el-input-number v-model="ev.charger_count" /></label
                  ><label
                    >单桩 kW<el-input-number
                      v-model="ev.rated_power_kw_per_charger" /></label
                  ><label
                    >利用率<el-input-number
                      v-model="ev.utilization_rate"
                      :step="0.1" /></label
                  ><label
                    >日均 kWh<el-input-number
                      v-model="ev.daily_energy_kwh" /></label
                  ><label
                    >起始小时<el-input-number
                      v-model="ev.charging_start_hour"
                      :min="0"
                      :max="23" /></label
                  ><label
                    >结束小时<el-input-number
                      v-model="ev.charging_end_hour"
                      :min="0"
                      :max="23" /></label
                  ><label
                    >到达小时<el-input-number
                      v-model="ev.arrival_hour"
                      :min="0"
                      :max="23" /></label
                  ><label
                    >离开小时<el-input-number
                      v-model="ev.departure_hour"
                      :min="0"
                      :max="23"
                  /></label>
                </div>
                <el-alert
                  v-if="
                    ev.arrival_hour > ev.departure_hour ||
                    ev.charging_start_hour > ev.charging_end_hour
                  "
                  title="当前配置为跨午夜时段"
                  type="info"
                  :closable="false"
                />
                <details>
                  <summary>24 小时规则曲线</summary>
                  <el-button
                    v-if="!ev.load_curve"
                    link
                    @click="ev.load_curve = Array(24).fill(0)"
                    >启用自定义曲线</el-button
                  ><template v-else
                    ><div class="hour-curve">
                      <label v-for="(_, i) in ev.load_curve" :key="i"
                        >{{ i }}h<el-input-number
                          v-model="ev.load_curve[i]"
                          :min="0"
                          :step="0.1"
                      /></label>
                    </div>
                    <el-button
                      link
                      type="danger"
                      @click="ev.load_curve = undefined"
                      >使用时段规则</el-button
                    ></template
                  >
                </details></MeasureCard
              >
              <MeasureCard
                v-show="selectedMeasure === 'GREEN_POWER'"
                title="绿电"
                code="GREEN_POWER"
                :enabled="enabled.GREEN_POWER"
                :summary="measureSummary('GREEN_POWER')"
                @toggle="enabled.GREEN_POWER = $event"
                ><el-alert
                  title="绿电仅影响碳属性与经济性，不是物理发电设备"
                  type="info"
                  :closable="false" />
                <div class="mini-form">
                  <label
                    >绿电比例<el-input-number
                      v-model="green.purchase_share"
                      :step="0.1" /></label
                  ><label
                    >合同总量 kWh<el-input-number
                      v-model="green.purchase_kwh" /></label
                  ><label
                    >排放因子 kgCO₂/kWh<el-input-number
                      v-model="green.emission_factor_kg_per_kwh"
                      :step="0.01" /></label
                  ><label
                    >溢价 元/kWh<el-input-number
                      v-model="green.premium_per_kwh"
                      :step="0.01"
                  /></label></div
              ></MeasureCard>
            </div>
          </main>
        </div>
      </section>

      <article class="panel simulation-section">
        <div class="panel-head">
          <div>
            <span>MARKET & FACTORS</span>
            <h2>市场与碳因子</h2>
          </div>
        </div>
        <div class="market-grid">
          <div>
            <span>电价来源</span
            ><strong>{{
              dynamicPrices ? "动态数据" : "固定参数/备用模式"
            }}</strong
            ><small>{{
              dynamicPrices
                ? `${dynamicPrices} 个逐时点`
                : "使用提交价格 fallback"
            }}</small>
          </div>
          <div>
            <span>购电价 fallback</span
            ><el-input-number
              v-model="electricityPrice"
              :min="0"
              :step="0.01"
            /><small>元/kWh</small>
          </div>
          <div>
            <span>上网电价 fallback</span
            ><el-input-number
              v-model="feedInTariff"
              :min="0"
              :step="0.01"
            /><small>元/kWh</small>
          </div>
          <div>
            <span>电网排放因子</span
            ><strong>{{
              dynamicFactors ? "动态数据" : "年度因子/备用模式"
            }}</strong
            ><small>{{
              dynamicFactors
                ? `${dynamicFactors} 个逐时点`
                : "按企业区域和年份解析"
            }}</small>
          </div>
          <div>
            <span>绿电参数</span
            ><strong>{{
              enabled.GREEN_POWER ? "临时配置" : "合同 Provider / 无配置"
            }}</strong
            ><small>Provider 优先级由后端决定</small>
          </div>
        </div>
      </article>

      <article class="panel simulation-section execution-panel">
        <div>
          <span>SIMULATION EXECUTION</span>
          <h2>仿真执行</h2>
          <p>后端仍是最终参数校验源，不展示伪造的进度百分比。</p>
          <small v-if="taskMeta"
            >创建
            {{
              taskMeta.started_at
                ? new Date(taskMeta.started_at).toLocaleString("zh-CN")
                : "暂无时间"
            }}
            · ScenarioVersion #{{ taskMeta.scenario_version_id || "—" }} ·
            {{
              Object.keys(taskMeta.parameter_snapshot_json.measures || {}).join(
                "、",
              ) || "无措施"
            }}</small
          >
        </div>
        <div v-if="validationErrors.length" class="validation-list">
          <b>配置校验未通过</b
          ><span v-for="x in validationErrors" :key="x">{{ x }}</span>
        </div>
        <div class="execution-actions">
          <el-button
            size="large"
            type="primary"
            :loading="running"
            :disabled="!scenarioId || validationErrors.length > 0"
            @click="confirmVisible = true"
            >配置摘要确认</el-button
          ><span v-if="taskId"
            >Task #{{ taskId }} ·
            <StatusTag :status="taskStatus || 'PENDING'" /></span
          ><el-button
            v-if="taskId && selectedVersion?.id && taskStatus === 'SUCCESS'"
            @click="
              router.push({
                path: '/reports',
                query: { scenario_version: selectedVersion.id, task: taskId },
              })
            "
            >进入报告中心</el-button
          >
        </div>
        <el-alert
          v-if="failure"
          :title="failure"
          type="error"
          show-icon
          :closable="false"
        />
      </article>

      <section v-if="hourly" class="simulation-section">
        <div class="section-heading">
          <span>HOURLY RESULTS</span>
          <h2>小时仿真结果</h2>
        </div>
        <el-alert
          v-if="maxBalanceError !== null && maxBalanceError > 1e-6"
          title="能源守恒误差超过 1e-6 kWh，请检查后端结果"
          type="error"
          show-icon
          :closable="false"
        />
        <div class="stat-grid result-stats">
          <StatCard
            label="总用能"
            :value="hourly.summary.load_base_kwh"
            unit="kWh"
          /><StatCard
            label="总购电"
            :value="hourly.summary.grid_power_kwh"
            unit="kWh"
          /><StatCard
            label="PV 发电"
            :value="hourly.summary.pv_generation_kwh"
            unit="kWh"
          /><StatCard
            label="风电发电"
            :value="hourly.summary.wind_generation_kwh"
            unit="kWh"
          /><StatCard
            label="可再生能源占比"
            :value="
              renewableShare === null
                ? null
                : `${(renewableShare * 100).toFixed(1)}%`
            "
          /><StatCard
            label="储能充 / 放"
            :value="`${hourly.summary.storage_charge_kwh} / ${hourly.summary.storage_discharge_kwh}`"
            unit="kWh"
          /><StatCard
            label="总碳排"
            :value="hourly.summary.carbon_emission_t"
            unit="tCO₂"
          /><StatCard label="总电费" :value="netCost" unit="元" /><StatCard
            label="最大守恒误差"
            :value="maxBalanceError"
            unit="kWh"
          />
        </div>
        <div class="simulation-chart-grid">
          <article class="panel">
            <h3>负荷与可再生能源</h3>
            <BaseChart :option="energyOption" />
          </article>
          <article class="panel">
            <h3>电网购电与上网</h3>
            <BaseChart :option="gridOption" />
          </article>
          <article class="panel">
            <h3>PV / 风电发电</h3>
            <BaseChart :option="generationOption" />
          </article>
          <article class="panel">
            <h3>储能 SOC</h3>
            <BaseChart :option="socOption" />
          </article>
          <article class="panel">
            <h3>储能充放电</h3>
            <BaseChart :option="storageOption" />
          </article>
          <article class="panel">
            <h3>小时碳排与绿电减排</h3>
            <BaseChart :option="carbonOption" />
          </article>
          <article class="panel">
            <h3>累计碳排</h3>
            <BaseChart :option="cumulativeCarbonOption" />
          </article>
          <article class="panel">
            <h3>累计电费与上网收益</h3>
            <BaseChart :option="costOption" />
          </article>
        </div>
      </section>
      <article v-else-if="annual" class="panel simulation-section">
        <div class="panel-head">
          <div>
            <span>ANNUAL RESULTS</span>
            <h2>年度仿真结果</h2>
          </div>
          <StatusTag :status="annual.task.status" />
        </div>
        <el-table :data="annual.results" empty-text="暂无结果"
          ><el-table-column prop="year" label="年份" /><el-table-column
            prop="electricity_base_kwh"
            label="原始用电 kWh" /><el-table-column
            prop="grid_power_kwh"
            label="购电 kWh" /><el-table-column
            prop="pv_generation_kwh"
            label="PV kWh" /><el-table-column
            prop="carbon_emission_t"
            label="碳排 tCO₂" /><el-table-column
            prop="carbon_reduction_t"
            label="减排 tCO₂" /><el-table-column
            prop="investment"
            label="投资" /><el-table-column
            prop="annual_benefit"
            label="年度收益"
        /></el-table>
      </article>
      <EmptyState
        v-else
        title="尚未执行仿真"
        description="完成配置并确认提交后查看真实结果"
      />
      <article class="panel simulation-section" data-testid="long-term-path">
        <div class="panel-head">
          <div>
            <span>长期碳排放路径</span>
            <h2>2024—2060 年长期路径推演</h2>
          </div>
          <el-button
            type="primary"
            :loading="longTermRunning"
            :disabled="!versionId"
            @click="runLongTerm"
            >执行长期推演</el-button
          >
        </div>
        <el-alert
          title="以当前场景版本和单年度小时级结果为基准，按年度状态与措施投产计划连续演化；不会重复执行37年逐小时仿真。"
          type="info"
          :closable="false"
        />
        <div class="form-grid">
          <label
            >起始年份<el-input-number
              v-model="longTermForm.start_year"
              :min="2024"
              :max="2060"
          /></label>
          <label
            >结束年份<el-input-number
              v-model="longTermForm.end_year"
              :min="2024"
              :max="2100"
          /></label>
          <label
            >目标达峰年份<el-input-number
              v-model="longTermForm.target_peak_year"
              :min="2024"
              :max="2060"
          /></label>
          <label
            >目标中和年份<el-input-number
              v-model="longTermForm.target_neutral_year"
              :min="2024"
              :max="2100"
          /></label>
          <label
            >年度负荷增长率<el-input-number
              v-model="longTermForm.annual_load_growth_rate"
              :step="0.005"
              :min="-0.2"
              :max="0.2"
          /></label>
          <label
            >综合能耗下降目标<el-input-number
              v-model="longTermForm.comprehensive_energy_target_rate"
              :step="0.01"
              :min="0"
              :max="1"
          /></label>
          <label
            >年度碳配额（吨）<el-input-number
              v-model="longTermForm.carbon_quota_t"
              :min="0"
          /></label>
          <label
            >电网因子年变化率<el-input-number
              v-model="longTermForm.annual_grid_factor_change_rate"
              :step="0.005"
              :min="-0.2"
              :max="0.2"
          /></label>
        </div>
        <template v-if="longTerm">
          <div class="summary-grid">
            <StatCard
              label="实际达峰年份"
              :value="longTerm.result_snapshot_json.actual_peak_year"
              :description="`目标 ${longTermForm.target_peak_year} 年`"
            />
            <StatCard
              label="实际中和年份"
              :value="
                longTerm.result_snapshot_json.actual_neutral_year ?? '未实现'
              "
              :description="longTerm.result_snapshot_json.neutrality_status"
            />
            <StatCard
              label="年度排放峰值"
              :value="longTerm.result_snapshot_json.peak_emission_t"
              unit="吨"
            />
            <StatCard
              label="期末预计碳排放"
              :value="longTerm.result_snapshot_json.emission_at_end_t"
              unit="吨"
            />
            <StatCard
              label="累计减排量"
              :value="longTerm.result_snapshot_json.cumulative_reduction_t"
              unit="吨"
            />
          </div>
          <el-alert
            v-if="!longTerm.result_snapshot_json.actual_neutral_year"
            :title="longTerm.result_snapshot_json.neutrality_status"
            type="warning"
            :closable="false"
          />
          <BaseChart :option="longTermOption" />
          <h3>关键措施投产时间点</h3>
          <el-timeline
            ><el-timeline-item
              v-for="item in longTerm.result_snapshot_json.key_milestones"
              :key="item.year"
              :timestamp="`${item.year}年`"
            >
              {{
                item.measures
                  .map((x) => measureNames[x as MeasureType] || x)
                  .join("、")
              }}
            </el-timeline-item></el-timeline
          >
          <el-table
            :data="longTerm.result_snapshot_json.annual"
            max-height="420"
          >
            <el-table-column
              prop="year"
              label="年份"
              width="80"
            /><el-table-column
              prop="energy_consumption_kwh"
              label="能源消费量（千瓦时）"
            />
            <el-table-column
              prop="renewable_generation_kwh"
              label="可再生能源发电量（千瓦时）"
            /><el-table-column
              prop="grid_import_kwh"
              label="电网购电量（千瓦时）"
            />
            <el-table-column
              prop="net_emission_t"
              label="净碳排放（吨）"
            /><el-table-column prop="carbon_reduction_t" label="减排量（吨）" />
            <el-table-column label="减排率"
              ><template #default="{ row }"
                >{{ (row.reduction_rate * 100).toFixed(2) }}%</template
              ></el-table-column
            >
            <el-table-column
              prop="quota_balance_t"
              label="配额盈余/缺口（吨）"
            /><el-table-column
              prop="cumulative_investment"
              label="累计投资（元）"
            />
            <el-table-column
              prop="operating_cost"
              label="运行成本（元）"
            /><el-table-column prop="carbon_cost" label="碳成本（元）" />
          </el-table>
          <section class="panel" data-testid="target-gap-analysis">
            <div class="panel-head">
              <div>
                <span>目标诊断</span>
                <h2>目标缺口与强化建议</h2>
              </div>
              <el-tag
                :type="
                  longTerm.result_snapshot_json.gap_analysis.targets_met
                    ? 'success'
                    : 'warning'
                "
                >{{
                  longTerm.result_snapshot_json.gap_analysis.targets_met
                    ? "目标已满足"
                    : "目标存在缺口"
                }}</el-tag
              >
            </div>
            <div class="summary-grid">
              <StatCard
                label="达峰延迟"
                :value="
                  longTerm.result_snapshot_json.gap_analysis.peak_delay_years
                "
                unit="年"
              />
              <StatCard
                label="目标年剩余排放"
                :value="
                  longTerm.result_snapshot_json.gap_analysis
                    .target_year_remaining_emission_t
                "
                unit="吨"
              />
              <StatCard
                label="中和排放缺口"
                :value="
                  longTerm.result_snapshot_json.gap_analysis.neutrality_gap_t
                "
                unit="吨"
              />
              <StatCard
                label="最大配额缺口"
                :value="
                  longTerm.result_snapshot_json.gap_analysis.max_quota_gap_t
                "
                unit="吨"
              />
            </div>
            <template
              v-if="!longTerm.result_snapshot_json.gap_analysis.targets_met"
            >
              <h3>主要未达标原因</h3>
              <el-collapse
                ><el-collapse-item
                  v-for="reason in longTerm.result_snapshot_json.gap_analysis
                    .reasons"
                  :key="reason.code"
                  :title="reason.title"
                  ><p>{{ reason.evidence }}</p></el-collapse-item
                ></el-collapse
              >
              <h3>分阶段强化建议</h3>
              <div class="chart-grid">
                <article
                  v-for="stage in longTerm.result_snapshot_json.gap_analysis
                    .recommendations"
                  :key="stage.stage"
                  class="panel"
                >
                  <h4>{{ stage.stage }}</h4>
                  <ul>
                    <li v-for="item in stage.items" :key="item">{{ item }}</li>
                  </ul>
                </article>
              </div>
              <h3>生成可选强化方案</h3>
              <el-alert
                title="以下参数属于示范仿真假设。执行后将生成独立的强化仿真情景，不覆盖原长期路径。"
                type="info"
                :closable="false"
              />
              <div class="form-grid">
                <label
                  >光伏年度新增容量（千瓦）<el-input-number
                    v-model="strengthenForm.pv_annual_addition_kw"
                    :min="0"
                /></label>
                <label
                  >风电年度新增容量（千瓦）<el-input-number
                    v-model="strengthenForm.wind_annual_addition_kw"
                    :min="0"
                /></label>
                <label
                  >储能扩容年份<el-input-number
                    v-model="strengthenForm.storage_expansion_year"
                    :min="2024"
                    :max="2060"
                /></label>
                <label
                  >储能扩容规模（千瓦时）<el-input-number
                    v-model="strengthenForm.storage_expansion_kwh"
                    :min="0"
                /></label>
                <label
                  >空调深化节能率<el-input-number
                    v-model="strengthenForm.additional_hvac_saving_rate"
                    :min="0"
                    :max="0.5"
                    :step="0.01"
                /></label>
                <label
                  >照明深化节能率<el-input-number
                    v-model="strengthenForm.additional_lighting_saving_rate"
                    :min="0"
                    :max="0.5"
                    :step="0.01"
                /></label>
                <label
                  >绿电采购比例<el-input-number
                    v-model="strengthenForm.green_power_ratio"
                    :min="0"
                    :max="1"
                    :step="0.05"
                /></label>
                <label
                  >CCER年度可用量（吨）<el-input-number
                    v-model="strengthenForm.annual_ccer_t"
                    :min="0"
                /></label>
              </div>
              <el-button
                type="primary"
                :loading="strengthenRunning"
                @click="runStrengthened"
                >生成并推演强化方案</el-button
              >
              <el-table
                v-if="strengthened"
                :data="[
                  { name: '原长期路径', run: longTerm },
                  { name: '强化仿真情景', run: strengthened },
                ]"
              >
                <el-table-column prop="name" label="方案" /><el-table-column
                  label="运行记录"
                  ><template #default="{ row }"
                    >#{{ row.run.id }}</template
                  ></el-table-column
                >
                <el-table-column label="实际达峰年份"
                  ><template #default="{ row }">{{
                    row.run.result_snapshot_json.actual_peak_year
                  }}</template></el-table-column
                >
                <el-table-column label="实际中和年份"
                  ><template #default="{ row }">{{
                    row.run.result_snapshot_json.actual_neutral_year ?? "未实现"
                  }}</template></el-table-column
                >
                <el-table-column label="期末剩余排放（吨）"
                  ><template #default="{ row }">{{
                    row.run.result_snapshot_json.emission_at_end_t
                  }}</template></el-table-column
                >
                <el-table-column label="累计减排（吨）"
                  ><template #default="{ row }">{{
                    row.run.result_snapshot_json.cumulative_reduction_t
                  }}</template></el-table-column
                >
                <el-table-column label="累计投资估算（万元）"
                  ><template #default="{ row }">{{
                    (
                      row.run.result_snapshot_json.cumulative_investment /
                      10000
                    ).toFixed(2)
                  }}</template></el-table-column
                >
                <el-table-column label="累计能源成本（元）"
                  ><template #default="{ row }">{{
                    row.run.result_snapshot_json.cumulative_energy_cost
                  }}</template></el-table-column
                >
                <el-table-column label="目标完成"
                  ><template #default="{ row }">{{
                    row.run.result_snapshot_json.gap_analysis.targets_met
                      ? "已满足"
                      : "存在缺口"
                  }}</template></el-table-column
                >
              </el-table>
              <el-alert
                v-if="strengthened"
                title="强化方案属于示范仿真情景。累计投资采用功能验证假设单价估算，不构成真实工程报价；实际中和年份是当前强化参数下的模型推演结果，不构成确定性承诺。"
                type="warning"
                :closable="false"
                show-icon
              />
            </template>
            <template v-else
              ><h3>目标已满足</h3>
              <ul>
                <li
                  v-for="item in longTerm.result_snapshot_json.gap_analysis
                    .success_factors"
                  :key="item"
                >
                  {{ item }}
                </li>
              </ul></template
            >
          </section>
        </template>
        <EmptyState
          v-else
          title="尚未执行长期路径推演"
          description="选择正式场景版本并确认目标、增长率、配额和措施实施年份后执行"
        />
      </article> </template
    ><EmptyState
      v-else
      title="暂无 Site"
      description="请先在数据中心创建 Site"
    />
    <el-dialog v-model="confirmVisible" title="确认仿真配置" width="620px"
      ><dl class="confirm-list">
        <dt>模式</dt>
        <dd>{{ mode === "HOURLY" ? "小时级" : "年度" }}</dd>
        <dt>场景版本</dt>
        <dd>
          {{ selectedScenario?.name }} /
          {{ selectedVersion ? `V${selectedVersion.version_number}` : "无" }}
        </dd>
        <dt>年份 / 时区</dt>
        <dd>{{ year }} / {{ timezone }}</dd>
        <dt>措施</dt>
        <dd>
          {{ measurePayload.map((x) => x.measure_type).join("、") || "无" }}
        </dd>
        <dt>配置性质</dt>
        <dd>
          {{
            mode === "HOURLY"
              ? "临时任务快照，不修改历史版本"
              : "年度仿真读取选定版本"
          }}
        </dd>
      </dl>
      <template #footer
        ><el-button @click="confirmVisible = false">取消</el-button
        ><el-button type="primary" @click="submit"
          >确认提交</el-button
        ></template
      ></el-dialog
    >
  </section>
</template>
