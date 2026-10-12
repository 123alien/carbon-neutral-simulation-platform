<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from "vue";
import Chart from "./Chart.vue";
type Annual = {
  year: number;
  net_emission_t: number;
  energy_consumption_kwh: number;
  renewable_generation_kwh: number;
  grid_import_kwh: number;
  carbon_reduction_t: number;
  quota_balance_t: number;
  cumulative_investment: number;
  operating_cost: number;
  carbon_cost: number;
};
type Path = {
  role: string;
  name: string;
  run_id: number;
  source_run_id: number | null;
  baseline_checksum: string;
  assumptions: Record<string, number>;
  measures: {
    measure_type: string;
    start_year: number;
    parameters_json: Record<string, number>;
  }[];
  prediction_interval: {
    confidence_level: number;
    interval_type: string;
    method: string;
    method_name: string;
    sample_size: number;
    data_class: string;
    calibration_notice: string;
    assumptions: Record<string, number>;
    points: { year: number; mean_t: number; lower_t: number; upper_t: number }[];
  } | null;
  result: {
    annual: Annual[];
    actual_peak_year: number;
    actual_neutral_year: number | null;
    peak_emission_t: number;
    emission_at_end_t: number;
    cumulative_reduction_t: number;
    cumulative_investment: number;
    cumulative_energy_cost: number;
    gap_analysis: any;
    key_milestones: { year: number; measures: string[] }[];
  };
};
const props = defineProps<{
  simulation:
    | { paths: Path[]; limitations?: string[]; data_notice?: string }
    | null
    | undefined;
}>();
const role = ref("low_carbon"),
  chosenYear = ref(2060),panelView=ref<'overview'|'comparison'|'report'>('overview');
const gapReport=ref<HTMLElement>(),milestoneReport=ref<HTMLElement>(),gapPaused=ref(false),milestonePaused=ref(false),comparisonPaused=ref(false);
let reportTimer:ReturnType<typeof setInterval>|undefined,comparisonTimer:ReturnType<typeof setInterval>|undefined,scenarioTimer:ReturnType<typeof setInterval>|undefined;
const holds=new WeakMap<HTMLElement,number>();
function advanceReport(el:HTMLElement|undefined,paused:boolean){
  if(!el||paused||el.scrollHeight<=el.clientHeight+2)return false;
  const hold=holds.get(el)||0;if(hold>0){holds.set(el,hold-1);return false}
  if(el.scrollTop+el.clientHeight>=el.scrollHeight-2){el.scrollTop=0;holds.set(el,32);return true}
  el.scrollTop+=1;return false;
}
function nextScenario(){if(!paths.value.length)return;const index=paths.value.findIndex(path=>path.role===role.value);role.value=paths.value[(index+1)%paths.value.length].role;gapReport.value?.scrollTo({top:0});milestoneReport.value?.scrollTo({top:0})}
function selectScenario(value:string){role.value=value;holds.delete(gapReport.value as HTMLElement);holds.delete(milestoneReport.value as HTMLElement);gapReport.value?.scrollTo({top:0});milestoneReport.value?.scrollTo({top:0})}
const paths = computed(() => props.simulation?.paths || []),
  selected = computed(
    () => paths.value.find((p) => p.role === role.value) || paths.value[0],
  ),
  annual = computed(() => selected.value?.result.annual || []),
  predictionInterval = computed(() => selected.value?.prediction_interval),
  gap = computed(() => selected.value?.result.gap_analysis),
  year = computed(
    () =>
      annual.value.find((r) => r.year === chosenYear.value) ||
      annual.value.at(-1),
  );
const autoplayYears=computed(()=>annual.value.map(r=>r.year));
onMounted(()=>{if(!matchMedia('(prefers-reduced-motion: reduce)').matches){reportTimer=setInterval(()=>{advanceReport(gapReport.value,gapPaused.value);const completed=advanceReport(milestoneReport.value,milestonePaused.value);if(panelView.value==='report'&&completed)nextScenario()},50);comparisonTimer=setInterval(()=>{if(panelView.value!=='comparison'||comparisonPaused.value||!autoplayYears.value.length)return;const index=autoplayYears.value.indexOf(chosenYear.value);chosenYear.value=autoplayYears.value[(index+1)%autoplayYears.value.length]},1000);scenarioTimer=setInterval(()=>{if(panelView.value==='report')return;nextScenario()},4000)}});
onBeforeUnmount(()=>{if(reportTimer)clearInterval(reportTimer);if(comparisonTimer)clearInterval(comparisonTimer);if(scenarioTimer)clearInterval(scenarioTimer)});
const fmt = (n: number | null | undefined, digits = 1) =>
  n == null
    ? "—"
    : n.toLocaleString("zh-CN", { maximumFractionDigits: digits });
const colors: Record<string, string> = {
  baseline: "#8aacc2",
  low_carbon: "#43e0ca",
  strengthened: "#ffd166",
};
const measureNames: Record<string, string> = {
  PV: "光伏扩容",
  WIND: "风电扩容",
  STORAGE: "储能扩容",
  HVAC: "空调节能",
  LIGHTING: "照明节能",
  GREEN_POWER: "绿电采购",
  CCER: "自愿减排量抵消",
};
const chart = computed(() => {
  const years = [
    ...new Set(paths.value.flatMap((p) => p.result.annual.map((r) => r.year))),
  ].sort((a, b) => a - b);
  return {
    animation: false,
    tooltip: { trigger: "axis", formatter:(params:any[])=>{
      const year=Number(params?.[0]?.axisValue);const point=predictionInterval.value?.points.find(p=>p.year===year);
      const rows=params.filter(p=>!p.seriesName.includes('预测下界')&&!p.seriesName.includes('模型预测区间')).map(p=>`${p.marker}${p.seriesName}：${fmt(Number(p.value))} tCO₂e`);
      if(point)rows.unshift(`<span style="color:#62dfd2">95%预测区间：${fmt(point.lower_t)}—${fmt(point.upper_t)} tCO₂e</span>`);
      return `<b>${year}年</b><br/>${rows.join('<br/>')}`;
    } },
    legend: { top: 0, data:['95%模型预测区间',...paths.value.map(p=>p.name)], textStyle: { color: "#b9d8e0" } },
    grid: { left: 70, right: 24, top: 40, bottom: 36 },
    xAxis: { type: "category", data: years.map(String), axisLabel: { color: "#8db9c7" } },
    yAxis: {
      type: "value",
      name: "净排放（tCO₂e）",
      nameTextStyle: { color: "#8db9c7" },
      axisLabel: { color: "#8db9c7" },
      splitLine: { lineStyle: { color: "#244e5e" } },
    },
    series: [
      ...(predictionInterval.value ? [{
        name:'95%预测下界',type:'line',stack:'prediction-band',symbol:'none',silent:true,
        data:years.map(y=>predictionInterval.value?.points.find(p=>p.year===y)?.lower_t??null),
        lineStyle:{opacity:0},areaStyle:{opacity:0},itemStyle:{opacity:0},tooltip:{show:false}
      },{
        name:'95%模型预测区间',type:'line',stack:'prediction-band',symbol:'none',silent:true,
        data:years.map(y=>{const p=predictionInterval.value?.points.find(p=>p.year===y);return p?Math.max(0,p.upper_t-p.lower_t):null}),
        lineStyle:{opacity:0},areaStyle:{color:'#43e0ca',opacity:.16},itemStyle:{color:'#43e0ca'},tooltip:{show:false}
      }] : []),
      ...paths.value.map((p) => {
      const result = p.result,
        assumptions = p.assumptions;
      const markers: any[] = [
        {
          name: "基准年",
          coord: [
            String(p.result.annual[0].year),
            p.result.annual[0].net_emission_t,
          ],
        },
        {
          name: "实际达峰",
          coord: [String(result.actual_peak_year), result.peak_emission_t],
        },
      ];
      if (result.actual_neutral_year !== null) {
        const row = result.annual.find(
          (r) => r.year === result.actual_neutral_year,
        );
        if (row)
          markers.push({
            name: "首次中和",
            coord: [String(row.year), row.net_emission_t],
          });
      }
      if(p.role===selected.value?.role){
        for(const milestone of result.key_milestones){
          const row=result.annual.find(r=>r.year===milestone.year)
          if(row)markers.push({name:milestone.measures.map(k=>measureNames[k]||'低碳措施').join('、'),coord:[String(row.year),row.net_emission_t]})
        }
      }
      return {
        name: p.name,
        type: "line",
        smooth: false,
        showSymbol: false,
        data: years.map(
          (y) =>
            result.annual.find((r) => r.year === y)?.net_emission_t ?? null,
        ),
        itemStyle: { color: colors[p.role] },
        lineStyle: { color: colors[p.role], width: 2 },
        markPoint: {
          symbol: "circle",
          symbolSize: 9,
          label: { show: false },
          data: markers,
        },
        markLine:
          p.role === selected.value?.role
            ? {
                symbol: "none",
                label: { color: "#aacece", formatter: "{b}" },
                data: [
                  {
                    name: "目标达峰",
                    xAxis: String(assumptions.target_peak_year),
                  },
                  {
                    name: "目标中和",
                    xAxis: String(assumptions.target_neutral_year),
                  },
                ],
              }
            : undefined,
      };
    })],
  };
});
const yearOption = computed(() => ({
  animation: false,
  tooltip: { trigger: "axis" },
  grid: { left: 45, right: 15, top: 12, bottom: 40 },
  xAxis: {
    type: "category",
    data: paths.value.map((p) => p.name),
    axisLabel: { color: "#9fc7d0" },
  },
  yAxis: {
    type: "value",
    axisLabel: { color: "#9fc7d0" },
    splitLine: { lineStyle: { color: "#244e5e" } },
  },
  series: [
    {
      type: "bar",
      barMaxWidth: 45,
      data: paths.value.map((p) => ({
        value:
          p.result.annual.find((r) => r.year === chosenYear.value)
            ?.net_emission_t ?? null,
        itemStyle: { color: colors[p.role] },
      })),
    },
  ],
}));
</script>
<template>
  <section class="simulation-workspace">
    <div v-if="!paths.length" class="panel empty simulation-empty">
      {{ simulation?.data_notice || "等待校园长期推演结果"
      }}<small>只读取当前校园的模块一运行记录，不借用其他园区数据。</small>
    </div>
    <template v-else
      ><div class="sim-heading">
        <div>
          <h2>校园低碳路径与目标分析</h2>
          <p>基准年完整年度运行＋年度状态演化 · 示范仿真数据 · 非学校实测</p>
        </div>
        <div class="sim-controls"><span>自动轮播 · 可点击切换</span><div class="scenario-playlist"><button v-for="p in paths" :key="p.role" :class="{active:p.role===role}" @click="selectScenario(p.role)">{{p.name}}</button></div></div>
      </div>
      <div class="sim-overview">
        <article :class="gap?.targets_met?'ok':'warn'"><small>目标判定</small><b>{{gap?.targets_met?'已满足':'存在缺口'}}</b><span>{{selected?.name}}</span></article>
        <article><small>实际达峰</small><b>{{selected?.result.actual_peak_year}}<i>年</i></b><span>目标 {{gap?.target_peak_year}}年</span></article>
        <article><small>首次中和</small><b>{{selected?.result.actual_neutral_year??'未实现'}}<i v-if="selected?.result.actual_neutral_year">年</i></b><span>目标 {{gap?.target_neutral_year}}年</span></article>
        <article><small>期末净排放</small><b>{{fmt(selected?.result.emission_at_end_t)}}<i>tCO₂e</i></b><span>中和缺口 {{fmt(gap?.neutrality_gap_t)}} 吨</span></article>
        <article><small>累计减排</small><b>{{fmt(selected?.result.cumulative_reduction_t)}}<i>tCO₂e</i></b><span>相对基准路径</span></article>
        <article><small>投资假设</small><b>{{fmt((selected?.result.cumulative_investment??0)/10000)}}<i>万元</i></b><span>非工程报价</span></article>
      </div>
      <nav class="sim-tabs" aria-label="低碳推演视图">
        <button :class="{active:panelView==='overview'}" @click="panelView='overview'">推演总览</button>
        <button :class="{active:panelView==='comparison'}" @click="panelView='comparison'">情景对比</button>
        <button :class="{active:panelView==='report'}" @click="panelView='report'">滚动报告</button>
      </nav>
      <div class="simulation-grid">
        <section v-if="panelView==='overview'" class="panel sim-curve">
          <h2>
            年度净碳排放路径 · {{ annual[0]?.year }}—{{ annual.at(-1)?.year }}
          </h2>
          <Chart :option="chart" />
          <div v-if="predictionInterval" class="confidence-meta">
            <b>{{ fmt(predictionInterval.confidence_level*100,0) }}% 模型预测区间</b>
            <span>{{ predictionInterval.method_name }} · {{ predictionInterval.sample_size.toLocaleString('zh-CN') }}次采样</span>
            <em>{{ predictionInterval.calibration_notice }}</em>
          </div>
          <p v-else class="confidence-missing">上游结果缺少可计算区间所需参数，当前不绘制置信带。</p>
          <p>曲线、节点及目标线读取模块一结果；阴影上下界由后端返回。{{ selected?.name }}：运行记录{{ selected?.run_id }}。</p>
        </section>
        <section v-if="panelView==='overview'" class="panel sim-targets">
          <h2>{{ selected?.name }} · 目标完成情况</h2>
          <strong :class="gap?.targets_met ? 'met' : 'unmet'">{{
            gap?.targets_met ? "当前参数下目标已满足" : "当前路径未满足全部目标"
          }}</strong>
          <dl>
            <dt>目标／实际达峰</dt>
            <dd>
              {{ gap?.target_peak_year }}／{{
                selected?.result.actual_peak_year
              }}年
            </dd>
            <dt>达峰延迟</dt>
            <dd>{{ gap?.peak_delay_years }}年</dd>
            <dt>目标／实际中和</dt>
            <dd>
              {{ gap?.target_neutral_year }}／{{
                selected?.result.actual_neutral_year ?? "未实现"
              }}
            </dd>
            <dt>目标年剩余排放</dt>
            <dd>{{ fmt(gap?.target_year_remaining_emission_t) }} tCO₂e</dd>
            <dt>中和缺口</dt>
            <dd>{{ fmt(gap?.neutrality_gap_t) }} tCO₂e</dd>
            <dt>年度排放峰值</dt>
            <dd>{{ fmt(selected?.result.peak_emission_t) }} tCO₂e</dd>
            <dt>期末净排放</dt>
            <dd>{{ fmt(selected?.result.emission_at_end_t) }} tCO₂e</dd>
          </dl>
          <p>
            中和阈值
            {{
              fmt(gap?.neutrality_threshold_t)
            }}
            tCO₂e。中和年份是当前假设下首次达到阈值的仿真结果，不是承诺。
          </p>
        </section>
        <section v-if="panelView==='comparison'" class="panel sim-comparison">
          <h2>原路径与强化情景对比</h2>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>指标</th>
                  <th v-for="p in paths" :key="p.role">{{ p.name }}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>实际达峰年</td>
                  <td v-for="p in paths" :key="p.role">
                    {{ p.result.actual_peak_year }}
                  </td>
                </tr>
                <tr>
                  <td>实际中和年</td>
                  <td v-for="p in paths" :key="p.role">
                    {{ p.result.actual_neutral_year ?? "未实现" }}
                  </td>
                </tr>
                <tr>
                  <td>期末净排放（吨）</td>
                  <td v-for="p in paths" :key="p.role">
                    {{ fmt(p.result.emission_at_end_t) }}
                  </td>
                </tr>
                <tr>
                  <td>累计减排（吨）</td>
                  <td v-for="p in paths" :key="p.role">
                    {{ fmt(p.result.cumulative_reduction_t) }}
                  </td>
                </tr>
                <tr>
                  <td>累计投资假设（万元）</td>
                  <td v-for="p in paths" :key="p.role">
                    {{ fmt(p.result.cumulative_investment / 10000) }}
                  </td>
                </tr>
                <tr>
                  <td>累计电网购电成本（万元）</td>
                  <td v-for="p in paths" :key="p.role">
                    {{ fmt(p.result.cumulative_energy_cost / 10000) }}
                  </td>
                </tr>
                <tr>
                  <td>目标完成</td>
                  <td v-for="p in paths" :key="p.role">
                    {{
                      p.result.gap_analysis?.targets_met
                        ? "已满足"
                        : "未全部满足"
                    }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            投资是模型假设，非真实工程报价；成本未完整覆盖直接能源替代、绿电溢价及新增储能工程，不能作为完整项目预算。
          </p>
        </section>
        <section v-if="panelView==='comparison'" class="panel sim-year" @mouseenter="comparisonPaused=true" @mouseleave="comparisonPaused=false">
          <h2>年度排放自动对比 · tCO₂e <small>{{comparisonPaused?'已暂停':'自动轮播'}}</small></h2>
          <select v-model.number="chosenYear" aria-label="比较年份" title="可手动定位年份；移出卡片后继续自动轮播">
            <option v-for="r in annual" :key="r.year" :value="r.year">
              {{ r.year }}年
            </option></select
          ><Chart :option="yearOption" />
        </section>
        <section v-if="panelView==='report'" ref="gapReport" class="panel sim-gap sim-report" @mouseenter="gapPaused=true" @mouseleave="gapPaused=false">
          <h2>
            {{ gap?.targets_met ? "关键成功因素" : "目标缺口原因与强化建议" }}
          </h2>
          <template v-if="gap?.targets_met"
            ><p v-for="factor in gap.success_factors" :key="factor">
              {{ factor }}
            </p></template
          ><template v-else
            ><div v-for="r in gap?.reasons" :key="r.code">
              <b>{{ r.title }}</b>
              <p>{{ r.evidence }}</p>
            </div>
            <div v-for="r in gap?.recommendations" :key="r.stage">
              <h3>{{ r.stage }}</h3>
              <p v-for="item in r.items" :key="item">{{ item }}</p>
            </div></template
          >
        </section>
        <section v-if="panelView==='report'" ref="milestoneReport" class="panel sim-milestones sim-report" @mouseenter="milestonePaused=true" @mouseleave="milestonePaused=false">
          <h2>投产计划与仿真假设</h2>
          <div
            v-for="m in selected?.result.key_milestones"
            :key="m.year"
            class="source"
          >
            <b>{{ m.year }}年</b>
            <p>
              {{
                m.measures.map((k) => measureNames[k] || "低碳措施").join("、")
              }}
            </p>
          </div>
          <p>
            负荷年增长
            {{
              fmt((selected?.assumptions.annual_load_growth_rate ?? 0) * 100)
            }}%；电网因子年变化
            {{
              fmt(
                (selected?.assumptions.annual_grid_factor_change_rate ?? 0) *
                  100,
              )
            }}%。
          </p>
          <p>年度数据窗口与大屏“本年截至当前时间”不同，不直接比较累计值。</p>
          <h3>{{ chosenYear }}年 · {{ selected?.name }}</h3>
          <p>
            用电 {{ fmt(year?.energy_consumption_kwh) }} kWh；可再生发电
            {{ fmt(year?.renewable_generation_kwh) }} kWh；购电
            {{ fmt(year?.grid_import_kwh) }} kWh。
          </p>
          <p>
            碳配额盈余／缺口 {{ fmt(year?.quota_balance_t) }} 吨（负数为缺口）。
          </p>
          <p>
            年度购电运行成本
            {{ fmt((year?.operating_cost ?? 0) / 10000) }} 万元；碳成本
            {{ fmt((year?.carbon_cost ?? 0) / 10000) }} 万元。
          </p>
          <p v-for="limitation in simulation?.limitations" :key="limitation">
            {{ limitation }}
          </p>
        </section>
      </div></template
    >
  </section>
</template>
<style scoped>
.simulation-workspace {
  margin-top: 0;
  --sim-accent:#43e0ca;
}
.sim-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 14px;
  padding:12px 15px;
  border:1px solid #285b69;
  background:linear-gradient(90deg,#0d3949,#092a38);
}
.sim-heading h2 {
  border: 0;
  margin: 0;
  padding: 0;
  font-size: 19px;
}
.sim-heading p {
  margin-bottom: 0;
}
.sim-controls{display:flex;align-items:center;gap:8px;color:#7fa9b2;font-size:10px}.scenario-playlist{display:flex;gap:4px}.scenario-playlist button{padding:6px 9px;border:1px solid #285d6b;background:#0a2d3b;color:#739da6;font-size:10px;transition:.25s}.scenario-playlist button.active{color:#eaffff;border-color:#3dd3c5;background:#12505a;box-shadow:0 0 10px #36cfc333}.sim-tabs{display:flex;gap:7px;margin:0 0 12px;padding:0;border:0}.sim-tabs button{padding:7px 16px;background:#0b3040;border:1px solid #2d6472;color:#91b7bf}.sim-tabs button.active{color:#5be4d5;border-color:#32bdb0;background:#124953;box-shadow:inset 3px 0 #46d8cc}
.simulation-grid {
  display: grid;
  align-items: start;
  grid-template-columns: repeat(12,minmax(0,1fr));
  gap: 14px;
}
.sim-overview{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px;margin-bottom:12px}.sim-overview article{position:relative;overflow:hidden;padding:10px 12px;border:1px solid #285565;background:linear-gradient(145deg,#103847,#092936)}.sim-overview article:after{content:"";position:absolute;right:-22px;top:-28px;width:70px;height:70px;border:1px solid #2f6773;border-radius:50%}.sim-overview small,.sim-overview b,.sim-overview span{display:block;position:relative;z-index:1}.sim-overview small{font-size:9px;color:#85adb6}.sim-overview b{font:700 19px ui-monospace,Consolas;color:#efffff;margin:5px 0}.sim-overview b i{font-size:8px;color:#68dcd1;font-style:normal;margin-left:4px}.sim-overview span{font-size:8px;color:#729ba5}.sim-overview article.ok{border-color:#278e7c}.sim-overview article.ok b{color:#57e6bc}.sim-overview article.warn{border-color:#9a7242}.sim-overview article.warn b{color:#ffc178}
.sim-curve {
  display: flex;
  flex-direction: column;
  min-height: 380px;
  grid-column:span 8;
}
.confidence-meta{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;margin:2px 0 4px;padding:8px 10px;border-left:3px solid #43e0ca;background:#0c3442;color:#9fc8d0;font-size:9px}.confidence-meta b{color:#65e5d6;font-size:11px}.confidence-meta span{align-self:center}.confidence-meta em{grid-column:1/-1;color:#f0c477;font-style:normal}.confidence-missing{padding:7px 10px;border-left:3px solid #d49a4b;background:#3f321c;color:#ffd28b}
.sim-targets{grid-column:span 4;min-height:380px;background:linear-gradient(155deg,#103746,#092a37)}
.sim-comparison{grid-column:span 8;min-height:310px}
.sim-year{grid-column:span 4}
.sim-gap,.sim-milestones{grid-column:span 6}
.sim-targets dl {
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 15px;
  font-size: 12px;
}
.sim-targets dt {
  color: #92b8c6;
}
.sim-targets dd {
  margin: 0;
  text-align: right;
}
.sim-targets strong {
  display: block;
  padding: 10px;
  background: #ffffff08;
}
.unmet {
  color: #ffbd75;
}
.met {
  color: #51dfbc;
}
.sim-year {
  display: flex;
  flex-direction: column;
  min-height: 300px;
}
.sim-year h2 small{float:right;color:#58d9cc;font-size:9px;font-weight:400}.sim-year h2 small:before{content:"●";margin-right:4px}.sim-year:hover h2 small{color:#ffc46e}
.table-scroll {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
th,
td {
  border-bottom: 1px solid #264b58;
  padding: 14px 10px;
  text-align: right;
  white-space: nowrap;
}
th:first-child,
td:first-child {
  text-align: left;
}
th {
  color: #7fd6ce;
}
.sim-gap {
  max-height: none;
}
.sim-report{height:430px;overflow-y:auto;scroll-behavior:auto;scrollbar-width:thin;scrollbar-color:#33808b #0a2b38;overscroll-behavior:contain}.sim-report:hover{border-color:#3b8e98}.sim-report:after{content:"自动轮播 · 悬停暂停";position:sticky;display:block;bottom:-1px;margin:8px -4px -4px;padding:6px;text-align:center;font-size:9px;color:#6fa2aa;background:linear-gradient(transparent,#0b2835 45%);pointer-events:none}
.sim-gap b {
  font-size: 13px;
  color: #c0e0e6;
}
h3 {
  font-size: 14px;
  color: #62d7ce;
}
select {
  padding: 8px;
  background: #103445;
  border: 1px solid #367386;
  color: #e0f7fb;
  border-radius: 3px;
}
.simulation-empty {
  min-height: 400px;
}
@media (max-width: 1100px) {
  .simulation-grid {
    grid-template-columns: 1fr;
  }
  .sim-curve,.sim-targets,.sim-comparison,.sim-year,.sim-gap,.sim-milestones{grid-column:auto}
  .sim-overview{grid-template-columns:repeat(3,1fr)}
  .sim-heading {
    flex-wrap: wrap;
  }
}
</style>
