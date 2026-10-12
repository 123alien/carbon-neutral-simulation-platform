<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, onDeactivated, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { EChartsOption } from "echarts";
import PageHeader from "@/components/PageHeader.vue";
import LoadingState from "@/components/LoadingState.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import BaseChart from "@/components/BaseChart.vue";
import StatusTag from "@/components/StatusTag.vue";
import { useSiteStore } from "@/stores/site";
import { scenariosApi } from "@/api/scenarios";
import { simulationApi } from "@/api/simulation";
import { carbonMarketApi } from "@/api/carbonMarket";
import type {
  CarbonCostAssessment,
  CarbonMarketBatchComparison,
  CarbonMarketScenario,
  CarbonMarketStatistics,
  Scenario,
  ScenarioVersion,
  SimulationBatch,
} from "@/types";
const route = useRoute(),
  router = useRouter(),
  siteStore = useSiteStore();
const loading = ref(true),
  busy = ref(false),
  error = ref<string | null>(null),
  operationError = ref<string | null>(null);
const scenarios = ref<Scenario[]>([]),
  versions = ref<ScenarioVersion[]>([]),
  batches = ref<SimulationBatch[]>([]),
  market = ref<CarbonMarketScenario | null>(null),
  statistics = ref<CarbonMarketStatistics | null>(null),
  assessments = ref<CarbonCostAssessment[]>([]),
  assessment = ref<CarbonCostAssessment | null>(null),
  batchComparison = ref<CarbonMarketBatchComparison | null>(null);
const versionId = ref<number | null>(null),
  taskId = ref<number | null>(null),
  batchId = ref<number | null>(null),
  region = ref("全国"),
  dates = ref<[Date, Date] | null>(null),
  indicator = ref("ALL");
const initialized = ref(false);
// Playback is a read-only cursor over API records; it never writes assessment inputs.
const cursor=ref(0),playing=ref(false),speed=ref(1500);
const statsLoading=ref(false),statsError=ref<string|null>(null),queriedAt=ref<string|null>(null);
let replayTimer:ReturnType<typeof setInterval>|undefined, statisticsRequest=0;
// China market's legacy timezone-less records denote Beijing local time.
const marketInstant=(value:string)=>Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)?value:value+'+08:00');
const sourceName=(value:string)=>value==='DEMO_SIMULATION'?'示范仿真数据':value;
const sortedRecords=computed(()=>(statistics.value?.records||[]).filter(r=>Number.isFinite(marketInstant(r.timestamp))).slice().sort((a,b)=>marketInstant(a.timestamp)-marketInstant(b.timestamp)));
const periods=computed(()=>[...new Set(sortedRecords.value.map(r=>marketInstant(r.timestamp)))]);
const cursorTime=computed(()=>periods.value[cursor.value]);
const replayRecords=computed(()=>sortedRecords.value.filter(r=>marketInstant(r.timestamp)<=cursorTime.value));
const currentRecords=computed(()=>sortedRecords.value.filter(r=>marketInstant(r.timestamp)===cursorTime.value));
const isDemoMarket=computed(()=>statistics.value?.region==='DEMO_REGION');
const periodLabel=(t:number|undefined)=>t==null?'暂无数据':new Date(t).toLocaleDateString('zh-CN',{timeZone:'Asia/Shanghai'});
const quoteFields=[
  {key:'carbon_price_per_t',name:'碳价',unit:'元/吨'},
  {key:'trading_volume_t',name:'成交量',unit:'吨'},
  {key:'trading_amount_yuan',name:'成交额',unit:'元'},
  {key:'ccer_price_per_t',name:'CCER价格',unit:'元/吨'},
  {key:'green_certificate_price',name:'绿证价格',unit:'元/张'},
] as const;
function pauseReplay(){if(replayTimer)clearInterval(replayTimer);replayTimer=undefined;playing.value=false;}
function playReplay(){
  if(periods.value.length<2||statsLoading.value)return;
  pauseReplay();
  if(cursor.value>=periods.value.length-1)cursor.value=0;
  playing.value=true;
  replayTimer=setInterval(()=>{
    cursor.value=Math.min(cursor.value+1,periods.value.length-1);
    if(cursor.value===periods.value.length-1)pauseReplay();
  },speed.value);
}
function quote(key:typeof quoteFields[number]['key']){
  const values=currentRecords.value.map(r=>r[key]).filter((v):v is number=>v!=null&&Number.isFinite(v));
  return new Set(values).size===1?values[0]:null;
}
const quoteConflict=computed(()=>quoteFields.some(({key})=>new Set(currentRecords.value.map(r=>r[key]).filter(v=>v!=null)).size>1));
watch(speed,()=>{if(playing.value)playReplay();});
watch([region,dates],pauseReplay,{deep:true});
function visibilityChanged(){if(document.hidden)pauseReplay();}
onMounted(()=>document.addEventListener('visibilitychange',visibilityChanged));
onDeactivated(pauseReplay);
onBeforeUnmount(()=>{pauseReplay();statisticsRequest++;document.removeEventListener('visibilitychange',visibilityChanged);});
const currentVersion = computed(() =>
  versions.value.find((v) => v.id === versionId.value),
);
const tasks = computed(() =>
  batches.value
    .flatMap((b) => b.items)
    .filter((i) => i.scenario_version_id === versionId.value && i.task_id)
    .map((i) => ({
      id: i.task_id!,
      label: `仿真任务${i.task_id} · ${statusName(i.status)}`,
    }))
    .filter((x, i, a) => a.findIndex((y) => y.id === x.id) === i),
);
const result = computed(() => assessment.value?.result_json);
const n = (v: number | null | undefined, d = 2) =>
  v == null
    ? "暂无数据"
    : v.toLocaleString("zh-CN", { maximumFractionDigits: d });
const time = (v: string) => new Date(v).toLocaleString("zh-CN");
const statusName = (value: string) =>
  (
    ({
      SUCCESS: "已完成",
      FAILED: "失败",
      PENDING: "待执行",
      RUNNING: "运行中",
      PARTIAL: "部分完成",
    }) as Record<string, string>
  )[value] || value;
const marketRegion = () =>
  region.value === "示范区域" ? "DEMO_REGION" : region.value;
const scenarioName = (id: number) => {
  const v = versions.value.find((x) => x.id === id),
    s = scenarios.value.find((x) => x.id === v?.scenario_id);
  return s?.name || `场景版本${id}`;
};
const seriesOption = (
  field: keyof CarbonMarketStatistics["records"][number],
  name: string,
  color: string,
): EChartsOption => ({
  animation: false,
  grid: { left: 65, right: 20, top: 45, bottom: 65 },
  xAxis: {
    type: "category",
    data: replayRecords.value
      .map((x) => periodLabel(marketInstant(x.timestamp))),
  },
  dataZoom:[{type:"inside"},{type:"slider",bottom:5}],
  yAxis: { type: "value", name: field==="green_certificate_price"?"元/张":field==="trading_volume_t"?"吨":"元/吨" },
  series: [
    {
      name,
      type: "line",
      smooth: false,
      connectNulls: false,
      itemStyle: { color },
      data: replayRecords.value
        .map((x) => x[field] == null ? null : x[field] as number),
    },
  ],
});
const carbonPriceOption = computed(() =>
    seriesOption("carbon_price_per_t", "碳价", "#2f8069"),
  ),
  volumeOption = computed(() =>
    seriesOption("trading_volume_t", "成交量", "#6384a8"),
  ),
  ccerOption = computed(() =>
    seriesOption("ccer_price_per_t", "CCER价格", "#bd7f37"),
  ),
  certificateOption = computed(() =>
    seriesOption("green_certificate_price", "绿证价格", "#658b4c"),
  );
const costOption = computed<EChartsOption>(() => ({
  series: [
    {
      name: "成本构成",
      type: "pie",
      radius: ["38%", "68%"],
      data: result.value
        ? [
            { name: "超额排放成本", value: result.value.excess_emission_cost },
            { name: "CCER成本", value: result.value.ccer_cost },
            { name: "绿证成本", value: result.value.green_certificate_cost },
            { name: "配额盈余价值", value: -result.value.quota_surplus_value },
          ]
        : [],
    },
  ],
}));
const emissionOption = computed<EChartsOption>(() => ({
  xAxis: { type: "category", data: ["原始碳排", "净碳排"] },
  yAxis: { type: "value", name: "tCO₂" },
  series: [
    {
      name: "碳排",
      type: "bar",
      data: result.value
        ? [result.value.gross_emission_t, result.value.net_carbon_emission_t]
        : [],
    },
  ],
}));
const compareOption = computed<EChartsOption>(() => ({
  grid: { left: 65, right: 20, top: 45, bottom: 70 },
  xAxis: {
    type: "category",
    axisLabel: { rotate: 20 },
    data: (batchComparison.value?.items || [])
      .filter((x) => x.carbon_market_result)
      .map((x) => scenarioName(x.scenario_version_id)),
  },
  yAxis: { type: "value", name: "综合碳成本" },
  series: [
    {
      name: "综合碳成本",
      type: "bar",
      data: (batchComparison.value?.items || [])
        .filter((x) => x.carbon_market_result)
        .map((x) => x.carbon_market_result!.comprehensive_carbon_cost),
    },
  ],
}));
async function initialize() {
  pauseReplay();
  initialized.value = false;
  loading.value = true;
  error.value = null;
  try {
    await siteStore.loadSites();
    if (!siteStore.currentSite) return;
    scenarios.value = await scenariosApi.list(
      siteStore.currentSite.enterprise_id,
    );
    versions.value = (
      await Promise.all(scenarios.value.map((s) => scenariosApi.versions(s.id)))
    ).flat();
    batches.value = await simulationApi.batches(
      siteStore.currentSite.enterprise_id,
    );
    const allAssessments = await carbonMarketApi.assessments();
    const validIds = new Set(versions.value.map((v) => v.id));
    const latestValid = allAssessments.find((item) =>
      validIds.has(item.scenario_version_id),
    );
    versionId.value =
      Number(route.query.scenario_version) ||
      latestValid?.scenario_version_id ||
      null;
    taskId.value =
      Number(route.query.task) ||
      (latestValid?.scenario_version_id === versionId.value
        ? latestValid.task_id
        : null);
    batchId.value = Number(route.query.batch) || null;
    if (typeof route.query.region === "string")
      region.value = route.query.region;
    else
      try {
        const rawRegion =
          (await simulationApi.enterprise(siteStore.currentSite.enterprise_id))
            .region || "全国";
        region.value = rawRegion === "DEMO_REGION" ? "示范区域" : rawRegion;
      } catch {
        region.value = "全国";
      }
    await loadStatistics();
    await loadEvaluation();
    initialized.value = true;
  } catch (e) {
    error.value = (e as { message?: string }).message || "碳市场页面加载失败";
  } finally {
    loading.value = false;
  }
}
async function loadData() {
  await Promise.all([loadStatistics(), loadEvaluation()]);
}
async function loadEvaluation() {
  market.value = null;
  assessment.value = null;
  operationError.value = null;
  if (versionId.value) {
    try {
      market.value = await carbonMarketApi.scenario(versionId.value);
    } catch {}
    assessments.value = await carbonMarketApi.assessments({
      scenario_version_id: versionId.value,
      task_id: taskId.value || undefined,
    });
    assessment.value = assessments.value[0] || null;
  }
  if (batchId.value) {
    try {
      batchComparison.value = await carbonMarketApi.batchComparison(
        batchId.value,
      );
    } catch {
      batchComparison.value = null;
    }
  }
}
async function loadStatistics() {
  pauseReplay();const request=++statisticsRequest;
  statsLoading.value=true;statsError.value=null;statistics.value=null;
  const [start,end]=dates.value||[];
  try{
    const value=await carbonMarketApi.statistics({region:marketRegion(),start:start?.toISOString(),end:end?.toISOString()});
    if(request!==statisticsRequest)return;
    statistics.value=value;cursor.value=Math.max(0,periods.value.length-1);
    queriedAt.value=new Date().toLocaleString('zh-CN');
  }catch(e){
    if(request===statisticsRequest)statsError.value=(e as {message?:string}).message||'市场数据查询失败';
  }finally{if(request===statisticsRequest)statsLoading.value=false;}
}
async function assess() {
  if (!versionId.value || !taskId.value) return;
  busy.value = true;
  operationError.value = null;
  try {
    assessment.value = await carbonMarketApi.assess({
      scenario_version_id: versionId.value,
      task_id: taskId.value,
    });
    assessments.value = [assessment.value, ...assessments.value];
  } catch (e) {
    const message = (e as { message?: string }).message || "碳市场评估失败";
    operationError.value = message.includes("no frozen carbon market snapshot")
      ? "所选仿真任务尚未冻结碳市场参数，请选择已有评估场景。"
      : message.includes("mismatch")
        ? "仿真任务与评估场景不匹配，请重新选择。"
        : message;
  } finally {
    busy.value = false;
  }
}
watch(versionId, async () => {
  if (!initialized.value) return;
  taskId.value = tasks.value[0]?.id || null;
  await loadEvaluation();
});
watch(taskId, async () => {
  if (!initialized.value) return;
  if (versionId.value) {
    assessments.value = await carbonMarketApi.assessments({
      scenario_version_id: versionId.value,
      task_id: taskId.value || undefined,
    });
    assessment.value = assessments.value[0] || null;
  }
});
onMounted(initialize);
</script>
<template>
  <section class="carbon-market-page">
    <PageHeader
      kicker="市场研究与成本分析"
      title="碳市场分析与碳成本评估"
      description="市场行情独立展示；场景参数及评估结果保持冻结，不随行情回放改变。"
      ><el-button :loading="loading" @click="initialize"
        >刷新</el-button
      ></PageHeader
    ><LoadingState v-if="loading" /><ErrorState
      v-else-if="error"
      :message="error"
      @retry="initialize"
    /><template v-else-if="siteStore.currentSite"
      ><article class="panel context-bar">
        <el-select v-model="versionId" placeholder="选择评估场景"
          ><el-option
            v-for="v in versions"
            :key="v.id"
            :value="v.id"
            :label="`${scenarioName(v.id)} · V${v.version_number} · #${v.id}`" /></el-select
        ><el-select v-model="taskId" placeholder="选择仿真任务"
          ><el-option
            v-for="t in tasks"
            :key="t.id"
            :value="t.id"
            :label="t.label" /></el-select
        ><el-select
          v-model="batchId"
          clearable
          placeholder="批次比较"
          @change="loadData"
          ><el-option
            v-for="b in batches"
            :key="b.id"
            :value="b.id"
            :label="`批量任务${b.id} · ${statusName(b.status)}`" /></el-select
        ><el-button
          type="primary"
          :loading="busy"
          :disabled="!versionId || !taskId || !market"
          @click="assess"
          >发起碳市场评估</el-button
        >
      </article>
      <el-alert
        v-if="operationError"
        :title="operationError"
        type="error"
        :closable="false"
      />
      <article class="panel">
        <div class="panel-head">
          <div>
            <span>场景市场参数快照</span>
            <h2>市场参数</h2>
          </div>
          <el-tag type="warning">当前评估场景</el-tag>
        </div>
        <div v-if="market" class="metric-grid" data-testid="frozen-market-parameters">
          <div>
            <span>碳价</span><b>{{ n(market.carbon_price_per_t) }} 元/tCO₂</b>
          </div>
          <div>
            <span>碳配额</span><b>{{ n(market.carbon_quota_t) }} tCO₂</b>
          </div>
          <div>
            <span>CCER 数量 / 价格</span
            ><b
              >{{ n(market.ccer_quantity_t) }} t /
              {{ n(market.ccer_price_per_t) }} 元/t</b
            >
          </div>
          <div>
            <span>绿证数量 / 价格</span
            ><b
              >{{ n(market.green_certificate_quantity) }} 张 /
              {{ n(market.green_certificate_price) }} 元/张</b
            >
          </div>
        </div>
        <EmptyState
          v-else
          title="当前场景尚未配置碳市场参数"
          description="可选择已有情景或执行新的碳成本评估。"
        />
      </article>
      <article class="panel" data-testid="market-statistics">
        <div class="panel-head">
          <div>
            <span>独立市场统计数据</span>
            <h2>市场指标趋势</h2>
          </div>
          <div class="filters">
            <el-input v-model="region" placeholder="市场/区域" /><el-date-picker
              v-model="dates"
              type="datetimerange"
            /><el-select v-model="indicator"
              ><el-option label="全部指标" value="ALL" /><el-option
                label="碳价"
                value="CARBON" /><el-option
                label="成交量"
                value="VOLUME" /><el-option
                label="CCER"
                value="CCER" /><el-option
                label="绿证"
                value="CERTIFICATE" /></el-select
            ><el-button :loading="statsLoading" @click="loadStatistics">查询</el-button>
          </div>
        </div>
        <LoadingState v-if="statsLoading" />
        <ErrorState v-else-if="statsError" :message="statsError" @retry="loadStatistics" />
        <template v-else-if="periods.length">
          <section class="market-replay" data-testid="market-replay">
            <div class="replay-heading">
              <h3>{{isDemoMarket?'示范行情回放':'历史行情回放'}}</h3>
              <el-tag type="warning">{{isDemoMarket?'示范仿真数据 · 非实时行情':'历史记录 · 非实时行情'}}</el-tag>
            </div>
            <p>按原始统计期依次展示，不插值、不随机生成价格；场景碳配额与评估结果不随回放变化。</p>
            <div class="replay-controls">
              <el-button type="primary" :disabled="periods.length<2" @click="playing?pauseReplay():playReplay()">{{playing?'暂停回放':'播放回放'}}</el-button>
              <el-button @click="pauseReplay();cursor=periods.length-1">查看全部</el-button>
              <label>播放速度 <select v-model.number="speed" aria-label="播放速度"><option :value="3000">慢速 · 3秒/期</option><option :value="1500">正常 · 1.5秒/期</option><option :value="750">快速 · 0.75秒/期</option></select></label>
              <label>统计期 <select v-model.number="cursor" aria-label="回放统计期" @change="pauseReplay"><option v-for="(period,index) in periods" :key="period" :value="index">{{periodLabel(period)}}</option></select></label>
              <span data-testid="replay-progress">{{cursor+1}} / {{periods.length}} 期 · {{playing?'播放中':cursor===periods.length-1?'已到最新统计期':'已暂停'}}</span>
            </div>
            <input class="replay-range" aria-label="行情回放进度" type="range" :min="0" :max="periods.length-1" v-model.number="cursor" @input="pauseReplay" :disabled="periods.length<2" />
            <div class="quote-cards">
              <div v-for="field in quoteFields" :key="field.key" :data-testid="'quote-'+field.key"><span>{{field.name}}</span><b>{{n(quote(field.key))}} <small v-if="quote(field.key)!=null">{{field.unit}}</small></b></div>
            </div>
            <p v-if="quoteConflict">同一统计期存在不同来源数值，相关卡片暂不合并，请查看下方数据明细。</p>
            <div class="replay-meta"><span>展示截至：{{periodLabel(cursorTime)}}</span><span>数据截至：{{periodLabel(periods.at(-1))}}</span><span>查询时间：{{queriedAt||'暂无数据'}}</span></div>
            <p class="replay-source">本期来源：{{[...new Set(currentRecords.map(r=>sourceName(r.source)))].join('；')||'未提供来源'}} · 统计时间按北京时间展示</p>
          </section>
          <div class="chart-grid">
            <BaseChart
              v-if="indicator === 'ALL' || indicator === 'CARBON'"
              :option="carbonPriceOption"
            /><BaseChart
              v-if="indicator === 'ALL' || indicator === 'VOLUME'"
              :option="volumeOption"
            /><BaseChart
              v-if="indicator === 'ALL' || indicator === 'CCER'"
              :option="ccerOption"
            /><BaseChart
              v-if="indicator === 'ALL' || indicator === 'CERTIFICATE'"
              :option="certificateOption"
            />
          </div>
          <el-table :data="replayRecords" max-height="420"
            ><el-table-column label="统计期" width="120"
              ><template #default="{ row }">{{
                new Date(marketInstant(row.timestamp)).toLocaleDateString("zh-CN", {
                  timeZone: "Asia/Shanghai",
                  year: "numeric",
                  month: "2-digit",
                })
              }}</template></el-table-column
            ><el-table-column label="碳价（元/吨）"
              ><template #default="{ row }">{{
                n(row.carbon_price_per_t)
              }}</template></el-table-column
            ><el-table-column label="碳市场成交量（t）"
              ><template #default="{ row }">{{
                n(row.trading_volume_t, 0)
              }}</template></el-table-column
            ><el-table-column label="碳市场成交额（元）"
              ><template #default="{ row }">{{
                n(row.trading_amount_yuan, 0)
              }}</template></el-table-column
            ><el-table-column label="CCER 成交量（t）"
              ><template #default="{ row }">{{
                n(row.ccer_volume_t, 0)
              }}</template></el-table-column
            ><el-table-column label="CCER 成交额（元）"
              ><template #default="{ row }">{{
                n(row.ccer_trading_amount_yuan, 0)
              }}</template></el-table-column
            ><el-table-column label="绿证核发/交易（个）"
              ><template #default="{ row }"
                >{{ n(row.green_certificate_issued_count, 0) }} /
                {{ n(row.green_certificate_traded_count, 0) }}</template
              ></el-table-column
            ><el-table-column
              label="数据来源"
              min-width="260"
              ><template #default="{row}">{{sourceName(row.source)}}</template></el-table-column></el-table></template
        ><EmptyState
          v-else
          title="暂无碳市场数据"
          description="当前市场及时间范围没有指标记录"
        />
      </article>
      <template v-if="assessment && result"
        ><section class="market-cards">
          <article>
            <span>配额状态</span
            ><StatusTag
              :status="
                result.quota_balance_t > 0
                  ? '配额盈余'
                  : result.quota_balance_t < 0
                    ? '配额不足'
                    : '基本平衡'
              "
            /><b>{{ n(result.quota_balance_t) }} tCO₂</b>
          </article>
          <article>
            <span>综合碳成本</span
            ><b>{{ n(result.comprehensive_carbon_cost) }} 元</b>
          </article>
          <article>
            <span>原始 / 净碳排</span
            ><b
              >{{ n(result.gross_emission_t) }} /
              {{ n(result.net_carbon_emission_t) }} tCO₂</b
            >
          </article>
          <article>
            <span>评估时间</span><b>{{ time(assessment.created_at) }}</b>
          </article>
        </section>
        <div class="analysis-grid">
          <article class="panel">
            <h2>配额分析</h2>
            <dl>
              <dt>实际碳排</dt>
              <dd>{{ n(result.gross_emission_t) }} tCO₂</dd>
              <dt>配额</dt>
              <dd>{{ n(result.carbon_quota_t) }} tCO₂</dd>
              <dt>盈余/缺口</dt>
              <dd>{{ n(result.quota_balance_t) }} tCO₂</dd>
              <dt>超额排放</dt>
              <dd>{{ n(result.excess_emission_before_offset_t) }} tCO₂</dd>
              <dt>盈余价值</dt>
              <dd>{{ n(result.quota_surplus_value) }} 元</dd>
              <dt>超额成本</dt>
              <dd>{{ n(result.excess_emission_cost) }} 元</dd>
            </dl>
          </article>
          <article class="panel">
            <h2>CCER 分析</h2>
            <template
              v-if="assessment.input_snapshot_json.market.ccer_quantity_t > 0"
              ><dl>
                <dt>可用数量</dt>
                <dd>
                  {{ n(assessment.input_snapshot_json.market.ccer_quantity_t) }}
                  t
                </dd>
                <dt>实际抵消</dt>
                <dd>{{ n(result.ccer_offset_t) }} t</dd>
                <dt>价格</dt>
                <dd>
                  {{
                    n(assessment.input_snapshot_json.market.ccer_price_per_t)
                  }}
                  元/t
                </dd>
                <dt>成本</dt>
                <dd>{{ n(result.ccer_cost) }} 元</dd>
                <dt>抵消前 / 净碳排</dt>
                <dd>
                  {{ n(result.gross_emission_t) }} /
                  {{ n(result.net_carbon_emission_t) }} tCO₂
                </dd>
              </dl></template
            ><EmptyState v-else title="当前场景未配置 CCER" />
          </article>
          <article class="panel">
            <h2>绿证分析（非绿电）</h2>
            <template
              v-if="
                assessment.input_snapshot_json.market
                  .green_certificate_quantity > 0
              "
              ><dl>
                <dt>绿证数量</dt>
                <dd>
                  {{
                    n(
                      assessment.input_snapshot_json.market
                        .green_certificate_quantity,
                    )
                  }}
                  张
                </dd>
                <dt>绿证价格</dt>
                <dd>
                  {{
                    n(
                      assessment.input_snapshot_json.market
                        .green_certificate_price,
                    )
                  }}
                  元/张
                </dd>
                <dt>绿证成本</dt>
                <dd>{{ n(result.green_certificate_cost) }} 元</dd>
              </dl>
              <p>
                绿证属于市场/政策分析层；绿电属于电力碳属性及经济性逻辑。
              </p></template
            ><EmptyState v-else title="当前场景未配置绿证" />
          </article>
        </div>
        <div class="chart-grid">
          <article class="panel">
            <h2>碳成本构成</h2>
            <BaseChart :option="costOption" />
          </article>
          <article class="panel">
            <h2>净碳排 / 原始碳排</h2>
            <BaseChart :option="emissionOption" />
          </article>
        </div>
        <article class="panel trace">
          <h2>数据来源与追溯</h2>
          <div>
            场景{{ currentVersion?.scenario_id }} · 场景版本{{
              assessment.scenario_version_id
            }}
            · 仿真任务{{ assessment.task_id }}
          </div>
          <div>
            冻结参数：碳价
            {{ n(assessment.input_snapshot_json.market.carbon_price_per_t) }}
            元/吨，碳配额
            {{ n(assessment.input_snapshot_json.market.carbon_quota_t) }}
            吨二氧化碳当量，CCER
            {{ n(assessment.input_snapshot_json.market.ccer_quantity_t) }}
            吨，绿证
            {{
              n(
                assessment.input_snapshot_json.market
                  .green_certificate_quantity,
                0,
              )
            }}
            张。
          </div>
          <el-alert
            title="历史结果基于任务执行时冻结快照，不读取当前市场配置替换历史结果。"
            type="info"
            :closable="false"
          /><el-button
            type="primary"
            @click="
              router.push({
                path: '/reports',
                query: {
                  scenario_version: assessment.scenario_version_id,
                  task: assessment.task_id,
                },
              })
            "
            >生成可行性报告</el-button
          >
        </article></template
      ><EmptyState
        v-else
        title="暂无碳成本评估"
        description="选择匹配的场景版本和仿真任务后发起评估"
      />
      <article v-if="batchComparison" class="panel">
        <h2>场景碳市场比较</h2>
        <BaseChart :option="compareOption" /><el-table
          :data="batchComparison.items"
          ><el-table-column label="场景"
            ><template #default="{ row }">{{
              scenarioName(row.scenario_version_id)
            }}</template></el-table-column
          ><el-table-column label="净碳排"
            ><template #default="{ row }"
              >{{
                n(row.carbon_market_result?.net_carbon_emission_t)
              }}
              tCO₂</template
            ></el-table-column
          ><el-table-column label="配额盈亏"
            ><template #default="{ row }"
              >{{ n(row.carbon_market_result?.quota_balance_t) }} tCO₂</template
            ></el-table-column
          ><el-table-column label="CCER 使用"
            ><template #default="{ row }"
              >{{ n(row.carbon_market_result?.ccer_offset_t) }} t</template
            ></el-table-column
          ><el-table-column label="绿证成本"
            ><template #default="{ row }"
              >{{
                n(row.carbon_market_result?.green_certificate_cost)
              }}
              元</template
            ></el-table-column
          ><el-table-column label="综合碳成本"
            ><template #default="{ row }"
              >{{
                n(row.carbon_market_result?.comprehensive_carbon_cost)
              }}
              元</template
            ></el-table-column
          ></el-table
        >
      </article></template
    ><EmptyState v-else title="暂无园区" />
  </section>
</template>
<style scoped>
.carbon-market-page .metric-grid b{color:#173e37;font:600 24px/1.35 "Bahnschrift","Segoe UI",sans-serif;font-variant-numeric:tabular-nums}
.carbon-market-page .metric-grid span{color:#526c65;font-size:13px}
.market-replay{padding:18px;border:1px solid #dbe8e1;background:#f5faf7;border-radius:10px;margin-top:16px;color:#23463d}
.replay-heading,.replay-controls,.replay-meta{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.replay-heading{justify-content:space-between}.replay-heading h3{margin:0;font-size:17px}
.market-replay p,.replay-meta{font-size:12px;color:#566f66;line-height:1.6}
.replay-controls label{font-size:13px}.replay-controls select{padding:7px;border:1px solid #bacfc4;background:white;border-radius:5px;color:#23463d}
.replay-controls>span{font-size:12px}.replay-range{width:100%;margin:18px 0;accent-color:#26866b;cursor:pointer}
.quote-cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:14px}
.quote-cards>div{padding:12px;background:white;border:1px solid #dfebe4;border-radius:7px}
.quote-cards span{display:block;color:#526c65;font-size:12px}
.quote-cards b{display:block;margin-top:7px;color:#173e37;font:600 22px/1.4 "Bahnschrift","Segoe UI",sans-serif}
.quote-cards small{font:normal 11px "Microsoft YaHei",sans-serif}
.replay-source{overflow-wrap:anywhere}.carbon-market-page .filters{flex-wrap:wrap}
@media(max-width:1200px){.quote-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
