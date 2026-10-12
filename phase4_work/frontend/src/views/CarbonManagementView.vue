<script setup lang="ts">
import {computed,onMounted,ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import type {EChartsOption} from 'echarts'
import {carbonApi,type CarbonFilters,type AccountingStandardValidation,type RegionalCarbonSummary} from '@/api/carbon'
import {useSiteStore} from '@/stores/site'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import BaseChart from '@/components/BaseChart.vue'
import LoadingState from '@/components/LoadingState.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import StatusTag from '@/components/StatusTag.vue'
import CampusSnapshotAccounting from '@/components/CampusSnapshotAccounting.vue'
import type {CarbonAccountingResult,CarbonAccountingRun,CarbonStatistics,CarbonTrendResponse,OrganizationNode} from '@/types'

type Granularity='day'|'month'|'year'
const route=useRoute(),router=useRouter(),siteStore=useSiteStore()
const loading=ref(true),detailLoading=ref(false),error=ref<string|null>(null)
const runs=ref<CarbonAccountingRun[]>([]),selectedRunId=ref<number|null>(null),results=ref<CarbonAccountingResult[]>([]),organizations=ref<OrganizationNode[]>([])
const siteCarbon=ref<CarbonTrendResponse|null>(null),energyStats=ref<CarbonStatistics|null>(null),scopeStats=ref<CarbonStatistics|null>(null),orgStats=ref<CarbonStatistics|null>(null)
const standardValidation=ref<AccountingStandardValidation|null>(null),regional=ref<RegionalCarbonSummary|null>(null)
const filters=ref<{range:[Date,Date]|null;granularity:Granularity;scope:string;energy:string;organization:number|null}>({range:null,granularity:'month',scope:'',energy:'',organization:null})
const energyLabels:Record<string,string>={electricity:'电力',natural_gas:'天然气',coal:'煤',oil:'油',heat:'热力'}
const levelLabels:Record<string,string>={ENTERPRISE:'企业',BUILDING_PARK:'园区',REGION:'区域'}
const siteTypeLabels:Record<string,string>={PARK:'产业园区',CAMPUS:'校园',PUBLIC_INSTITUTION:'公共机构'}
const currentRun=computed(()=>runs.value.find(x=>x.id===selectedRunId.value)||null)
const currentOrg=computed(()=>organizations.value.find(x=>x.id===filters.value.organization)||null)
const queryParams=computed<CarbonFilters>(()=>({granularity:filters.value.granularity,scope:filters.value.scope||undefined,energy_type:filters.value.energy||undefined,start_time:filters.value.range?.[0].toISOString(),end_time:filters.value.range?.[1].toISOString()}))
const scopedResults=computed(()=>results.value)
const total=computed(()=>siteCarbon.value?.total_emission_t??null)
const scope1=computed(()=>siteCarbon.value?.scope.SCOPE_1??(total.value===null?null:0))
const scope2=computed(()=>siteCarbon.value?.scope.SCOPE_2??(total.value===null?null:0))
const majorEnergy=computed(()=>{const rows=Object.entries(siteCarbon.value?.energy||{});return rows.length?energyLabels[rows.sort((a,b)=>b[1]-a[1])[0][0]]||rows[0][0]:null})
const comparison=computed(()=>{const trend=siteCarbon.value?.trend||[];if(trend.length<2)return null;const previous=trend.at(-2)!.emission_t,current=trend.at(-1)!.emission_t;return previous===0?null:(current-previous)/previous*100})
const latestAccounting=computed(()=>currentRun.value?.created_at||runs.value[0]?.created_at||null)
const accountingLabel=(run:CarbonAccountingRun)=>`${new Date(run.period_start).getFullYear()}年度园区碳排放核算`
const organizationName=(id:number|null|undefined)=>id?organizations.value.find(x=>x.id===id)?.name||`节点 ${id}`:'企业未分配'
const parentName=(node:OrganizationNode)=>node.parent_id?organizationName(node.parent_id):'—'
const pct=(value:number,base:number|null)=>base&&base!==0?`${(value/base*100).toFixed(1)}%`:'—'
const number=(value:number,digits=2)=>value.toLocaleString('zh-CN',{minimumFractionDigits:digits,maximumFractionDigits:digits})
const date=(value:string)=>new Date(value).toLocaleString('zh-CN')
const axisDates=(value:string)=>new Date(value).toLocaleDateString('zh-CN',{year:'numeric',month:'2-digit',day:filters.value.granularity==='day'?'2-digit':undefined})

const totalTrendOption=computed<EChartsOption>(()=>({grid:{left:65,right:25,top:44,bottom:35},xAxis:{type:'category',data:(siteCarbon.value?.trend||[]).map(x=>axisDates(x.timestamp))},yAxis:{type:'value',name:'tCO₂'},series:[{name:'总碳排',type:'line',smooth:true,symbolSize:7,areaStyle:{color:'rgba(45,138,114,.12)'},lineStyle:{color:'#2d8a72',width:3},data:(siteCarbon.value?.trend||[]).map(x=>x.emission_t)}]}))
const scopeCompositionOption=computed<EChartsOption>(()=>({tooltip:{trigger:'item'},series:[{name:'排放范围构成',type:'pie',radius:['48%','72%'],data:[...(scope1.value===null?[]:[{name:'直接排放',value:scope1.value}]),...(scope2.value===null?[]:[{name:'间接排放',value:scope2.value}])],color:['#cb7d3d','#327fa8']}]}))
const scopeTrendOption=computed<EChartsOption>(()=>{const items=scopeStats.value?.items||[],dates=[...new Set(items.map(x=>axisDates(x.bucket_start)))];return {grid:{left:62,right:25,top:50,bottom:35},xAxis:{type:'category',data:dates},yAxis:{type:'value',name:'tCO₂'},series:['SCOPE_1','SCOPE_2'].map((scope,i)=>({name:scope==='SCOPE_1'?'直接排放':'间接排放',type:'bar',stack:'scope',itemStyle:{color:i?'#327fa8':'#cb7d3d'},data:dates.map(d=>items.filter(x=>axisDates(x.bucket_start)===d&&x.dimension_key===scope).reduce((n,x)=>n+x.emission_t,0))}))}})
const energyCompositionOption=computed<EChartsOption>(()=>({tooltip:{trigger:'item'},series:[{name:'能源排放',type:'pie',radius:'68%',data:Object.entries(siteCarbon.value?.energy||{}).map(([name,value])=>({name:energyLabels[name]||name,value}))}]}))
const energyTrendOption=computed<EChartsOption>(()=>{const items=energyStats.value?.items||[],dates=[...new Set(items.map(x=>axisDates(x.bucket_start)))],keys=[...new Set(items.map(x=>x.dimension_key))];return {grid:{left:62,right:25,top:50,bottom:35},xAxis:{type:'category',data:dates},yAxis:{type:'value',name:'tCO₂'},series:keys.map(key=>({name:energyLabels[key]||key,type:'line',smooth:true,data:dates.map(d=>items.filter(x=>axisDates(x.bucket_start)===d&&x.dimension_key===key).reduce((n,x)=>n+x.emission_t,0))}))}})
const orgRows=computed(()=>{const sums=new Map<string,number>();for(const item of orgStats.value?.items||[])sums.set(item.dimension_key,(sums.get(item.dimension_key)||0)+item.emission_t);return [...sums].map(([key,emission_t])=>{const node=organizations.value.find(x=>String(x.id)===key);return {id:key,name:node?.name||key,level:node?.level||'ENTERPRISE',parent:node?parentName(node):'—',emission_t}}).sort((a,b)=>b.emission_t-a.emission_t)})
const orgOption=computed<EChartsOption>(()=>({grid:{left:90,right:28,top:35,bottom:35},xAxis:{type:'value',name:'tCO₂'},yAxis:{type:'category',data:orgRows.value.map(x=>x.name)},series:[{name:'组织节点碳排',type:'bar',data:orgRows.value.map(x=>x.emission_t),itemStyle:{color:'#527f73',borderRadius:[0,5,5,0]}}]}))
const regionalOption=computed<EChartsOption>(()=>({grid:{left:110,right:28,top:35,bottom:35},xAxis:{type:'value',name:'吨二氧化碳当量'},yAxis:{type:'category',data:(regional.value?.sites||[]).map(x=>x.site_name)},series:[{name:'碳排放量',type:'bar',data:(regional.value?.sites||[]).map(x=>x.total_emission_t),itemStyle:{color:'#397d69'}}]}))

async function initialize(){loading.value=true;error.value=null;try{await siteStore.loadSites();const requested=Number(route.query.site);if(requested){const site=siteStore.sites.find(x=>x.id===requested);if(site)siteStore.selectSite(site)}await loadSiteContext()}catch(e){error.value=(e as {message?:string}).message||'碳排放数据加载失败'}finally{loading.value=false}}
async function loadSiteContext(){const site=siteStore.currentSite;if(site?.code==='HBUE')return;if(!site){runs.value=[];siteCarbon.value=null;return}[organizations.value,runs.value,standardValidation.value,regional.value]=await Promise.all([carbonApi.organizations(site.enterprise_id),carbonApi.runs({enterprise_id:site.enterprise_id}),carbonApi.standardValidation(),carbonApi.regionalCarbon(site.enterprise_id)]);filters.value.organization=site.organization_node_id||null;selectedRunId.value=runs.value[0]?.id||null;await loadDetails()}
async function loadDetails(){const site=siteStore.currentSite;detailLoading.value=true;error.value=null;try{if(!site)return;siteCarbon.value=await carbonApi.siteStatistics(site.id,queryParams.value);if(!selectedRunId.value){results.value=[];energyStats.value=scopeStats.value=orgStats.value=null;return}const id=selectedRunId.value,resultFilter={energy_type:filters.value.energy||undefined,scope:filters.value.scope||undefined,organization_node_id:filters.value.organization||undefined,start_time:queryParams.value.start_time,end_time:queryParams.value.end_time},statFilter={granularity:filters.value.granularity,timezone:site.timezone,...resultFilter};[results.value,energyStats.value,scopeStats.value,orgStats.value]=await Promise.all([carbonApi.results(id,resultFilter),carbonApi.statistics(id,{...statFilter,dimension:'energy'}),carbonApi.statistics(id,{...statFilter,dimension:'scope'}),carbonApi.statistics(id,{...statFilter,dimension:'organization'})])}catch(e){error.value=(e as {message?:string}).message||'核算明细加载失败'}finally{detailLoading.value=false}}
async function selectSite(id:number){siteStore.selectSite(siteStore.sites.find(x=>x.id===id)||null);await router.replace({query:{site:id}});await loadSiteContext()}
watch(selectedRunId,(value,old)=>value!==old&&old!==null&&loadDetails())
onMounted(initialize)
</script>

<template><section>
  <PageHeader kicker="碳排放管理" title="园区碳排放核算" description="按园区、排放范围、能源类型、时间和组织层级进行核算与追溯。"><el-button :loading="loading||detailLoading" @click="initialize"><el-icon><Refresh/></el-icon>刷新</el-button></PageHeader>
  <CampusSnapshotAccounting v-if="!loading&&siteStore.currentSite?.code==='HBUE'" :site-id="siteStore.currentSite.id"/>
  <template v-else>
  <div class="carbon-toolbar">
    <el-select :model-value="siteStore.currentSite?.id" placeholder="选择园区" @change="selectSite"><el-option v-for="site in siteStore.sites" :key="site.id" :label="site.name" :value="site.id"/></el-select>
    <el-select v-model="filters.organization" clearable placeholder="全部组织节点"><el-option v-for="org in organizations" :key="org.id" :label="`${org.name} · ${levelLabels[org.level]||org.level}`" :value="org.id"/></el-select>
    <el-date-picker v-model="filters.range" type="datetimerange" start-placeholder="开始时间" end-placeholder="结束时间"/>
    <el-select v-model="filters.granularity"><el-option label="按日" value="day"/><el-option label="按月" value="month"/><el-option label="按年" value="year"/></el-select>
    <el-select v-model="filters.scope" clearable placeholder="全部排放范围"><el-option label="直接排放（范围一）" value="SCOPE_1"/><el-option label="间接排放（范围二）" value="SCOPE_2"/></el-select>
    <el-select v-model="filters.energy" clearable placeholder="全部能源"><el-option v-for="(label,key) in energyLabels" :key="key" :label="label" :value="key"/></el-select>
    <el-button type="primary" @click="loadDetails">查询</el-button>
  </div>
  <LoadingState v-if="loading"/>
  <ErrorState v-else-if="error" :message="error" @retry="initialize"/>
  <template v-else-if="siteStore.currentSite">
    <div class="carbon-context"><span>{{siteStore.currentSite.name}}</span><span>{{currentOrg?`${currentOrg.name} · ${levelLabels[currentOrg.level]||currentOrg.level}`:'企业范围'}}</span><span>时区 {{siteStore.currentSite.timezone}}</span></div>
    <EmptyState v-if="!runs.length&&siteCarbon?.data_status==='NO_DATA'" title="暂无核算数据" description="完成园区碳排放核算后，结果将在本页展示"/>
    <template v-else>
      <div class="stat-grid carbon-stats">
        <StatCard label="总碳排放量" :value="total" unit="tCO₂" hint="当前筛选范围" tone="green"/>
        <StatCard label="直接排放" :value="scope1" unit="tCO₂e" :hint="scope1===null?'暂无核算数据':`范围一 · ${pct(scope1,total)}`" tone="amber"/>
        <StatCard label="间接排放" :value="scope2" unit="tCO₂e" :hint="scope2===null?'暂无核算数据':`范围二 · ${pct(scope2,total)}`" tone="blue"/>
        <StatCard label="当期变化" :value="comparison===null?null:`${comparison>=0?'+':''}${comparison.toFixed(1)}%`" :hint="comparison===null?'暂无可比数据':'与上一聚合周期相比'" tone="slate"/>
      </div>
      <div class="carbon-summary-strip"><div><span>主要排放能源</span><strong>{{majorEnergy||'暂无数据'}}</strong></div><div><span>最近核算时间</span><strong>{{latestAccounting?date(latestAccounting):'暂无数据'}}</strong></div><div><span>当前核算周期</span><strong>{{currentRun?accountingLabel(currentRun):'暂无核算记录'}}</strong></div><div><span>核算方法</span><strong>园区综合能源碳核算</strong><small>覆盖直接排放与间接排放，详细来源可追溯</small></div></div>

      <div class="chart-grid carbon-chart-grid">
        <article class="panel"><div class="panel-head"><div><span>排放趋势</span><h2>总碳排放趋势</h2></div></div><BaseChart :option="totalTrendOption" :loading="detailLoading" :empty="!siteCarbon?.trend.length"/></article>
        <article class="panel"><div class="panel-head"><div><span>排放构成</span><h2>直接排放与间接排放</h2></div></div><BaseChart :option="scopeCompositionOption" :loading="detailLoading" :empty="total===null"/></article>
        <article class="panel"><div class="panel-head"><div><span>分类趋势</span><h2>排放范围变化趋势</h2></div></div><BaseChart :option="scopeTrendOption" :loading="detailLoading" :empty="!scopeStats?.items.length"/></article>
        <article class="panel"><div class="panel-head"><div><span>能源结构</span><h2>能源排放构成</h2></div></div><BaseChart :option="energyCompositionOption" :loading="detailLoading" :empty="!Object.keys(siteCarbon?.energy||{}).length"/></article>
        <article class="panel wide"><div class="panel-head"><div><span>能源趋势</span><h2>各能源排放趋势</h2></div></div><BaseChart :option="energyTrendOption" :loading="detailLoading" :empty="!energyStats?.items.length"/></article>
      </div>

      <article class="panel carbon-section"><div class="panel-head"><div><span>排放明细</span><h2>能源排放分析</h2></div><span class="panel-note">活动量与排放因子单位按核算口径展示</span></div>
        <el-table :data="scopedResults" empty-text="暂无核算数据"><el-table-column prop="energy_type" label="能源"><template #default="{row}">{{energyLabels[row.energy_type]||row.energy_type}}</template></el-table-column><el-table-column label="原始活动数据" min-width="140"><template #default="{row}">{{number(row.original_activity_value)}} {{row.original_activity_unit}}</template></el-table-column><el-table-column label="标准化活动数据" min-width="150"><template #default="{row}">{{number(row.activity_value)}} {{row.activity_unit}}</template></el-table-column><el-table-column label="碳排量" min-width="125"><template #default="{row}">{{number(row.emission_t)}} tCO₂</template></el-table-column><el-table-column label="占比"><template #default="{row}">{{pct(row.emission_t,total)}}</template></el-table-column><el-table-column label="排放因子" min-width="160"><template #default="{row}">{{number(row.emission_factor)}} {{row.factor_unit}}</template></el-table-column><el-table-column prop="factor_source" label="来源" min-width="140"><template #default="{row}">{{row.factor_source||'未注明'}}</template></el-table-column><el-table-column prop="factor_version" label="版本"/></el-table>
      </article>

      <div class="org-layout carbon-section"><article class="panel"><div class="panel-head"><div><span>组织分析</span><h2>组织层级分析</h2></div><span class="panel-note">最高排放：{{orgRows[0]?.name||'暂无数据'}}</span></div><BaseChart :option="orgOption" :loading="detailLoading" :empty="!orgRows.length" height="360px"/></article><article class="panel"><div class="panel-head"><div><span>层级关系</span><h2>节点关系与占比</h2></div></div><el-table :data="orgRows" empty-text="暂无组织核算数据"><el-table-column prop="name" label="节点"/><el-table-column label="层级"><template #default="{row}">{{levelLabels[row.level]||row.level}}</template></el-table-column><el-table-column prop="parent" label="上级"/><el-table-column label="碳排"><template #default="{row}">{{number(row.emission_t)}} tCO₂e</template></el-table-column><el-table-column label="占比"><template #default="{row}">{{pct(row.emission_t,orgStats?.total_emission_t??null)}}</template></el-table-column></el-table></article></div>

      <article v-if="regional" class="panel carbon-section"><div class="panel-head"><div><span>区域案例</span><h2>区域级碳排放汇总与排名</h2></div><el-tag type="info">{{regional.data_notice}}</el-tag></div><p>汇总产业园区、校园和公共机构案例，所有结果按园区组织节点隔离后聚合。</p><BaseChart :option="regionalOption" :empty="!regional.sites.length" height="320px"/><el-table :data="regional.sites" empty-text="暂无区域案例"><el-table-column type="index" label="排名" width="70"/><el-table-column prop="site_name" label="园区/机构"/><el-table-column label="类型"><template #default="{row}">{{siteTypeLabels[row.site_type]||row.site_type}}</template></el-table-column><el-table-column label="碳排放量"><template #default="{row}">{{row.total_emission_t==null?'暂无数据':`${number(row.total_emission_t)} 吨二氧化碳当量`}}</template></el-table-column><el-table-column label="状态"><template #default="{row}">{{row.data_status==='OK'?'已有核算结果':'暂无数据'}}</template></el-table-column></el-table></article>

      <article v-if="standardValidation" class="panel carbon-section"><div class="panel-head"><div><span>标准核算验证</span><h2>{{standardValidation.standard}}</h2></div><el-tag type="warning">{{standardValidation.data_notice}}</el-tag></div><el-alert :title="standardValidation.claim" type="info" :closable="false"/><p>核算边界：{{standardValidation.boundary}}</p><el-alert :title="`GB/T 32151适用性：${standardValidation.applicability.reason}`" type="warning" :closable="false" show-icon/><p>适用对象：{{standardValidation.applicability.object_type}} · 行业分部：{{standardValidation.applicability.industry_profile||'未选择（禁止强行匹配）'}} · <a :href="standardValidation.applicability.official_catalog" target="_blank" rel="noopener">国家标准目录</a></p><el-table :data="standardValidation.mapping"><el-table-column prop="energy_type" label="能源类型"/><el-table-column prop="boundary" label="核算边界"/><el-table-column label="活动数据"><template #default="{row}">{{number(row.activity_value)}} {{row.activity_unit}}</template></el-table-column><el-table-column label="排放因子"><template #default="{row}">{{row.factor}} {{row.factor_unit}}</template></el-table-column><el-table-column prop="formula" label="计算公式" min-width="180"/><el-table-column label="计算结果"><template #default="{row}">{{number(row.emission_t)}} 吨二氧化碳当量</template></el-table-column></el-table><p><b>可复算示例：</b>{{standardValidation.recalculable_example.formula}} = {{number(standardValidation.recalculable_example.emission_t)}} 吨二氧化碳当量。</p></article>

      <article class="panel carbon-section"><div class="panel-head"><div><span>历史核算</span><h2>核算批次</h2></div><el-select v-model="selectedRunId" placeholder="选择核算批次"><el-option v-for="run in runs" :key="run.id" :label="accountingLabel(run)" :value="run.id"/></el-select></div><el-table :data="runs" highlight-current-row empty-text="暂无核算记录" @row-click="(row:CarbonAccountingRun)=>selectedRunId=row.id"><el-table-column label="核算周期" min-width="180"><template #default="{row}">{{accountingLabel(row)}}</template></el-table-column><el-table-column label="组织层级"><template #default>{{currentOrg?levelLabels[currentOrg.level]||currentOrg.level:'企业'}}</template></el-table-column><el-table-column label="时间范围" min-width="260"><template #default="{row}">{{date(row.period_start)}} — {{date(row.period_end)}}</template></el-table-column><el-table-column label="状态"><template #default="{row}"><StatusTag :status="row.status"/></template></el-table-column><el-table-column label="核算时间" min-width="170"><template #default="{row}">{{date(row.created_at)}}</template></el-table-column><el-table-column label="核算方法" min-width="190"><template #default>园区综合能源碳核算</template></el-table-column></el-table></article>

      <article class="panel carbon-section"><div class="panel-head"><div><span>核算追溯</span><h2>排放因子追溯</h2></div><span class="panel-note">当前核算批次 · {{scopedResults.length}} 条明细</span></div><el-table :data="scopedResults" empty-text="暂无因子明细"><el-table-column type="expand"><template #default="{row}"><dl class="factor-expand"><dt>核算公式</dt><dd>{{row.formula}}</dd><dt>标准参考</dt><dd>{{row.standard_basis}}</dd><dt>活动数据来源</dt><dd>{{row.activity_source||'未注明'}}</dd><dt>记录时间</dt><dd>{{date(row.timestamp)}}</dd></dl></template></el-table-column><el-table-column label="能源"><template #default="{row}">{{energyLabels[row.energy_type]||row.energy_type}}</template></el-table-column><el-table-column label="原始活动数据" min-width="145"><template #default="{row}">{{number(row.original_activity_value)}} {{row.original_activity_unit}}</template></el-table-column><el-table-column label="标准化活动数据" min-width="155"><template #default="{row}">{{number(row.activity_value)}} {{row.activity_unit}}</template></el-table-column><el-table-column label="排放因子" min-width="170"><template #default="{row}">{{number(row.emission_factor,6)}} {{row.factor_unit}}</template></el-table-column><el-table-column prop="factor_source" label="因子来源" min-width="150"><template #default="{row}">{{row.factor_source||'未注明'}}</template></el-table-column><el-table-column prop="factor_version" label="版本"/><el-table-column label="排放范围"><template #default="{row}">{{row.scope==='SCOPE_1'?'直接排放':'间接排放'}}</template></el-table-column></el-table></article>
    </template>
  </template>
  <EmptyState v-else title="暂无园区" description="请先在数据中心创建园区并完成关联"/>
  </template>
</section></template>
