<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useSiteStore } from "@/stores/site";
import { buildingsApi } from "@/api/buildings";
import { devicesApi } from "@/api/devices";
import { meteringPointsApi } from "@/api/meteringPoints";
import { dataSourcesApi } from "@/api/dataSources";
import { weatherApi } from "@/api/weather";
import PageHeader from "@/components/PageHeader.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import EmptyState from "@/components/EmptyState.vue";
import StatusTag from "@/components/StatusTag.vue";
import BaseChart from "@/components/BaseChart.vue";
import type { EChartsOption } from "echarts";
import DataSourceWizard from "@/components/data-config/DataSourceWizard.vue";
import ImportWizard from "@/components/data-config/ImportWizard.vue";
import ExternalDataStatus from "@/components/data-config/ExternalDataStatus.vue";
import type {
  AcquisitionOverview,
  Building,
  DataSource,
  DataSourceDetail,
  DataSourceRuntime,
  Device,
  MeteringPoint,
  WeatherSite,
} from "@/types";
const sites = useSiteStore(),
  loading = ref(true),
  error = ref<string | null>(null),
  stage = ref("target"),
  sourceDialog = ref(false),
  buildings = ref<Building[]>([]),
  devices = ref<Device[]>([]),
  meters = ref<MeteringPoint[]>([]),
  sources = ref<DataSource[]>([]),
  details = ref<Record<number, DataSourceDetail>>({}),
  runtimes = ref<Record<number, DataSourceRuntime>>({}),
  weatherSites = ref<WeatherSite[]>([]),
  overview = ref<AcquisitionOverview | null>(null),
  buildingId = ref<number | null>(null),
  deviceId = ref<number | null>(null),
  meterId = ref<number | null>(null);
const steps = [
  {
    key: "target",
    label: "接入对象",
    desc: "选择当前园区及需要接入数据的建筑、设备或计量点",
  },
  {
    key: "source",
    label: "数据源",
    desc: "配置物联网、标准接口、第三方、文件或人工数据入口",
  },
  {
    key: "collect",
    label: "数据采集与导入",
    desc: "执行自动采集，或预览并确认文件导入",
  },
  {
    key: "quality",
    label: "数据质量结果",
    desc: "查看自动清洗、分级校验、异常和隔离结果",
  },
];
const sourceType = (v: string) =>
  (
    ({
      FILE: "文件",
      REST_API: "标准接口",
      MQTT: "物联网",
      THIRD_PARTY: "第三方系统",
      MANUAL: "人工录入",
    }) as Record<string, string>
  )[v] || v;
const selectedBuilding = computed(
    () => buildings.value.find((x) => x.id === buildingId.value) || null,
  ),
  selectedDevice = computed(
    () => devices.value.find((x) => x.id === deviceId.value) || null,
  ),
  selectedMeter = computed(
    () => meters.value.find((x) => x.id === meterId.value) || null,
  );
async function refreshLive() {
  const automatic = sources.value.filter((s) => s.schedule_enabled);
  if (!automatic.length) return;
  const pairs = await Promise.all(
    automatic.map(
      async (s) =>
        [
          s.id,
          await dataSourcesApi.detail(s.id),
          await dataSourcesApi.runtime(s.id),
        ] as const,
    ),
  );
  for (const [id, detail, runtime] of pairs) {
    details.value[id] = detail;
    runtimes.value[id] = runtime;
  }
}
async function load() {
  loading.value = true;
  error.value = null;
  try {
    await sites.loadSites();
    const site = sites.currentSite;
    if (!site) {
      buildings.value = [];
      devices.value = [];
      meters.value = [];
      sources.value = [];
      return;
    }
    [
      buildings.value,
      devices.value,
      meters.value,
      sources.value,
      weatherSites.value,
      overview.value,
    ] = await Promise.all([
      buildingsApi.list(site.id),
      devicesApi.bySite(site.id),
      meteringPointsApi.list({ site_id: site.id }),
      dataSourcesApi.list(site.enterprise_id, site.id),
      weatherApi.sites(site.enterprise_id),
      dataSourcesApi.overview(site.enterprise_id, site.id),
    ]);
    details.value = Object.fromEntries(
      await Promise.all(
        sources.value.map(
          async (s) => [s.id, await dataSourcesApi.detail(s.id)] as const,
        ),
      ),
    );
    await refreshLive();
  } catch (e) {
    error.value = (e as { message?: string }).message || "数据接入信息加载失败";
  } finally {
    loading.value = false;
  }
}
async function chooseSite(id: number) {
  sites.selectSite(sites.sites.find((x) => x.id === id) || null);
  buildingId.value = deviceId.value = meterId.value = null;
  await load();
}
async function testSource(row: DataSource) {
  try {
    const r = await dataSourcesApi.test(row.id);
    ElMessage[r.success ? "success" : "warning"](r.message);
  } catch (e) {
    ElMessage.error((e as { message?: string }).message || "连接测试失败");
  }
}
async function sync(row: DataSource) {
  try {
    const r = await dataSourcesApi.syncNow(row.id);
    ElMessage.success(`采集完成：写入 ${r.inserted}，隔离 ${r.quarantined}`);
    await load();
  } catch (e) {
    ElMessage.error((e as { message?: string }).message || "采集失败");
  }
}
async function remove(row: DataSource) {
  try {
    await ElMessageBox.confirm(
      `确认删除数据源“${row.name}”？存在已绑定设备或事实数据时系统会拒绝删除。`,
      "删除数据源",
      { type: "warning" },
    );
    await dataSourcesApi.remove(row.id);
    await load();
  } catch (e) {
    if (e !== "cancel" && e !== "close")
      ElMessage.error((e as { message?: string }).message || "删除失败");
  }
}
const metricName = (v: string) =>
  (
    ({
      power_kw: "光伏实时功率",
      energy_kwh: "累计发电量",
      voltage_v: "电压",
      current_a: "电流",
      device_temperature_c: "设备温度",
      active_power_kw: "风电有功功率",
      wind_speed_m_s: "风速",
      soc_pct: "储能荷电状态",
      hvac_power_kw: "空调功率",
      water_m3: "用水量",
    }) as Record<string, string>
  )[v] || v;
const latestPower = (id: number) =>
  details.value[id]?.latest_records.find((x) => ["power_kw", "active_power_kw", "hvac_power_kw", "water_m3"].includes(x.metric_name));
const waterRows = computed(() => Object.values(details.value).flatMap(x => x.latest_records).filter(x => x.metric_name === "water_m3").slice(0, 24).reverse());
const waterOption = computed<EChartsOption>(() => ({
  grid: { left: 58, right: 20, top: 35, bottom: 42 },
  xAxis: { type: "category", data: waterRows.value.map(x => formatUtc(x.timestamp)) },
  yAxis: { type: "value", name: "立方米" },
  series: [{ name: "用水量", type: "line", smooth: true, data: waterRows.value.map(x => x.value), itemStyle: { color: "#2c86b8" } }],
}));
const formatUtc = (value: string | null | undefined) => {
  if (!value) return "尚未采集";
  const normalized = /Z$|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`;
  return new Date(normalized).toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour12: false,
  });
};
let liveTimer = 0;
watch(() => sites.currentSite?.id, load);
onMounted(async () => {
  await load();
  liveTimer = window.setInterval(
    () => refreshLive().catch(() => undefined),
    5000,
  );
});
onBeforeUnmount(() => window.clearInterval(liveTimer));
</script>
<template>
  <section>
    <PageHeader
      kicker="园区多源数据入口"
      title="数据接入"
      description="选择已有园区对象，配置数据来源并完成采集、自动清洗、分级校验和入库。"
      ><el-button @click="load">刷新</el-button></PageHeader
    >
    <ExternalDataStatus />
    <div class="context">
      <label>当前园区</label
      ><el-select
        :model-value="sites.currentSite?.id"
        placeholder="选择园区"
        @change="chooseSite"
        ><el-option
          v-for="s in sites.sites"
          :key="s.id"
          :label="s.name"
          :value="s.id" /></el-select
      ><StatusTag v-if="sites.currentSite" :status="sites.currentSite.status" />
    </div>
    <LoadingState v-if="loading" /><ErrorState
      v-else-if="error"
      :message="error"
      @retry="load"
    /><EmptyState
      v-else-if="!sites.currentSite"
      title="暂无园区"
      description="请先在园区管理中创建园区、建筑、设备和计量点"
      ><router-link to="/park"
        ><el-button type="primary">进入园区管理</el-button></router-link
      ></EmptyState
    ><template v-else
      ><nav class="flow" aria-label="数据接入流程">
        <button
          v-for="(item, index) in steps"
          :key="item.key"
          :class="{ active: stage === item.key }"
          @click="stage = item.key"
        >
          <i>{{ index + 1 }}</i
          ><span
            ><b>{{ item.label }}</b
            ><small>{{ item.desc }}</small></span
          >
        </button>
      </nav>
      <article v-if="stage === 'target'" class="panel">
        <h2>选择接入对象</h2>
        <el-alert
          title="数据源至少关联当前园区，可进一步精确到建筑、设备或计量点。"
          type="info"
          :closable="false"
        />
        <div class="target-grid">
          <label
            >建筑（可选）<el-select v-model="buildingId" clearable
              ><el-option
                v-for="b in buildings"
                :key="b.id"
                :label="b.name"
                :value="b.id" /></el-select></label
          ><label
            >设备（可选）<el-select v-model="deviceId" clearable
              ><el-option
                v-for="d in devices"
                :key="d.id"
                :label="d.name"
                :value="d.id" /></el-select></label
          ><label
            >计量点（可选）<el-select v-model="meterId" clearable
              ><el-option
                v-for="m in meters"
                :key="m.id"
                :label="`${m.name} · ${m.unit}`"
                :value="m.id" /></el-select
          ></label>
        </div>
        <el-button type="primary" @click="stage = 'source'"
          >下一步：配置数据源</el-button
        >
      </article>
      <article v-else-if="stage === 'source'" class="panel">
        <div class="head">
          <div>
            <h2>数据源</h2>
            <p>当前园区共 {{ overview?.source_count ?? 0 }} 个数据源。物联网状态每5秒读取一次后台实际结果。</p>
          </div>
          <el-button type="primary" @click="sourceDialog = true"
            >新增数据源</el-button
          >
        </div>
        <el-alert title="以下自动采集链均使用规则驱动的示范仿真数据，不代表真实设备现场数据。" type="info" :closable="false" show-icon />
        <section v-for="row in sources.filter(item => item.schedule_enabled)" :key="`live-${row.id}`" class="live-source">
          <header><div><h3>{{ row.name }}</h3><p>接入方式：{{ sourceType(row.source_type) }} · 设备：{{ details[row.id]?.binding.devices[0]?.name || '园区级接口' }}</p></div><StatusTag :status="runtimes[row.id]?.runtime_status === 'RUNNING' ? '在线' : runtimes[row.id]?.runtime_status || '待启动'" /></header>
          <div class="live-kpis"><span>最近采集<b>{{ formatUtc(details[row.id]?.status.last_received_at) }}</b></span><span>最新指标<b>{{ latestPower(row.id) ? `${metricName(latestPower(row.id)!.metric_name)} ${latestPower(row.id)?.value} ${latestPower(row.id)?.unit}` : '暂无数据' }}</b></span><span>近24小时<b>{{ details[row.id]?.status.received_last_24h ?? 0 }} 条</b></span><span>数据完整率<b>{{ details[row.id]?.validation.total_records ? `${(details[row.id].validation.quality_rate * 100).toFixed(1)}%` : '暂无数据' }}</b></span><span>异常数据<b>{{ details[row.id]?.validation.quarantined_records ?? 0 }} 条</b></span><span>质量校验<b>{{ details[row.id]?.validation.total_records ? (details[row.id].validation.quality_rate >= .95 ? '正常' : '需处理') : '暂无数据' }}</b></span></div>
          <el-collapse><el-collapse-item title="查看最近遥测记录"><el-table :data="details[row.id]?.latest_records || []" size="small" empty-text="尚未收到遥测"><el-table-column label="采集时间"><template #default="scope">{{ formatUtc(scope.row.timestamp) }}</template></el-table-column><el-table-column label="指标"><template #default="scope">{{ metricName(scope.row.metric_name) }}</template></el-table-column><el-table-column label="数值"><template #default="scope">{{ scope.row.value }} {{ scope.row.unit }}</template></el-table-column><el-table-column prop="quality" label="质量状态" /></el-table></el-collapse-item></el-collapse>
        </section>
        <el-table :data="sources" empty-text="暂无数据源"
          ><el-table-column prop="name" label="名称" /><el-table-column
            label="类型"
            ><template #default="{ row }">{{
              sourceType(row.source_type)
            }}</template></el-table-column
          ><el-table-column label="关联对象"
            ><template #default="{ row }">{{
              row.metering_point_id
                ? `计量点 #${row.metering_point_id}`
                : row.device_id
                  ? `设备 #${row.device_id}`
                  : row.building_id
                    ? `建筑 #${row.building_id}`
                    : "园区"
            }}</template></el-table-column
          ><el-table-column label="最近采集"
            ><template #default="{ row }">{{
              row.last_sync_at
                ? new Date(row.last_sync_at).toLocaleString("zh-CN")
                : "尚未采集"
            }}</template></el-table-column
          ><el-table-column label="状态"
            ><template #default="{ row }"
              ><StatusTag :status="row.status" /></template></el-table-column
          ><el-table-column label="操作" width="250"
            ><template #default="{ row }"
              ><el-button link @click="testSource(row)">测试连接</el-button
              ><el-button link @click="sync(row)">立即采集</el-button
              ><el-button link type="danger" @click="remove(row)"
                >删除</el-button
              ></template
            ></el-table-column
          ></el-table
        >
        <article v-if="waterRows.length" class="water-panel"><h3>园区用水趋势</h3><p>工作日、午间高峰及建筑用途差异由规则模型驱动；数据性质：示范仿真数据。</p><BaseChart :option="waterOption" :empty="!waterRows.length" height="280px" /></article>
      </article>
      <article v-else-if="stage === 'collect'" class="panel">
        <h2>数据采集与导入</h2>
        <p>
          接口和物联网数据可在数据源列表执行采集；文件数据在此预览、校验并确认入库。
        </p>
        <ImportWizard
          :enterprise-id="sites.currentSite.enterprise_id"
          :weather-sites="weatherSites"
          @confirmed="load"
        />
      </article>
      <article v-else class="panel">
        <h2>数据质量结果</h2>
        <div class="quality-summary">
          <span
            >有效率
            <b>{{
              overview?.quality_rate == null
                ? "暂无数据"
                : `${(overview.quality_rate * 100).toFixed(1)}%`
            }}</b></span
          ><span
            >隔离记录 <b>{{ overview?.quarantined ?? 0 }}</b></span
          ><span
            >最近数据
            <b>{{
              overview?.latest_data_at
                ? new Date(overview.latest_data_at).toLocaleString("zh-CN")
                : "暂无数据"
            }}</b></span
          >
        </div>
        <el-table :data="sources" empty-text="暂无质量结果"
          ><el-table-column prop="name" label="数据源" /><el-table-column
            label="有效记录"
            ><template #default="{ row }">{{
              details[row.id]?.validation.valid_records ?? "暂无数据"
            }}</template></el-table-column
          ><el-table-column label="异常隔离"
            ><template #default="{ row }">{{
              details[row.id]?.validation.quarantined_records ?? "暂无数据"
            }}</template></el-table-column
          ><el-table-column label="警告"
            ><template #default="{ row }">{{
              details[row.id]?.validation.warning_records ?? "暂无数据"
            }}</template></el-table-column
          ><el-table-column label="质量状态"
            ><template #default="{ row }"
              ><StatusTag
                :status="
                  (details[row.id]?.validation.quality_rate ?? 0) >= 0.95
                    ? '正常'
                    : '需处理'
                " /></template></el-table-column></el-table
        ><el-collapse
          ><el-collapse-item
            v-for="row in sources"
            :key="row.id"
            :title="`${row.name} · 异常和待处理数据`"
            ><el-table
              :data="details[row.id]?.validation_logs || []"
              empty-text="暂无异常"
              ><el-table-column
                prop="created_at"
                label="时间" /><el-table-column
                prop="validation_stage"
                label="校验阶段" /><el-table-column
                prop="message"
                label="原因" /><el-table-column
                prop="disposition"
                label="处理结果" /></el-table></el-collapse-item
        ></el-collapse></article></template
    ><el-dialog v-model="sourceDialog" title="新增数据源" width="780px"
      ><DataSourceWizard
        :enterprise-id="sites.currentSite?.enterprise_id || 0"
        :site="sites.currentSite"
        :buildings="selectedBuilding ? [selectedBuilding] : buildings"
        :devices="selectedDevice ? [selectedDevice] : devices"
        :meters="selectedMeter ? [selectedMeter] : meters"
        @saved="
          () => {
            sourceDialog = false;
            load();
          }
        "
    /></el-dialog>
  </section>
</template>
<style scoped>
.context,
.head,
.quality-summary {
  display: flex;
  align-items: center;
  gap: 12px;
}
.context {
  margin-bottom: 14px;
}
.context .el-select {
  width: 300px;
}
.flow {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}
.flow button {
  display: flex;
  text-align: left;
  gap: 10px;
  padding: 14px;
  border: 1px solid #d8e3df;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
}
.flow button.active {
  border-color: #23876d;
  background: #edf8f4;
}
.flow i {
  font-style: normal;
  color: #14745c;
}
.flow span {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.flow small,
.head p,
.panel > p {
  color: #6b7d77;
}
.head {
  justify-content: space-between;
}
.target-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin: 16px 0;
}
.target-grid label {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.quality-summary {
  margin: 12px 0;
  flex-wrap: wrap;
}
.quality-summary span {
  padding: 12px 18px;
  background: #eff6f4;
  border-radius: 8px;
}
.live-source{margin:12px 0 18px;padding:16px;border:1px solid #cfe4dc;border-radius:10px;background:#f7fbfa}.live-source header{display:flex;justify-content:space-between;align-items:center}.live-source h3,.live-source p{margin:0 0 6px}.live-kpis{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin:12px 0}.live-kpis span{padding:10px;background:#fff;border-radius:7px;color:#60736d}.live-kpis b{display:block;margin-top:6px;color:#183f35}
.water-panel{margin-top:18px;padding-top:14px;border-top:1px solid #d8e3df}.water-panel h3,.water-panel p{margin:0 0 8px}.water-panel p{color:#6b7d77}
@media (max-width: 900px) {
  .flow,
  .target-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
