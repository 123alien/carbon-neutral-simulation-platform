<script setup lang="ts">
import {computed,defineAsyncComponent,onMounted,ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {useSiteStore} from '@/stores/site'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
const route=useRoute(),router=useRouter(),sites=useSiteStore()
const stage=ref(String(route.query.stage||'baseline'))
const components={
  data:defineAsyncComponent(()=>import('@/views/DataAccessView.vue')),
  accounting:defineAsyncComponent(()=>import('@/views/CarbonManagementView.vue')),
  baseline:defineAsyncComponent(()=>import('@/views/ScenariosView.vue')),
  target:defineAsyncComponent(()=>import('@/views/RecommendationsView.vue')),
  recommend:defineAsyncComponent(()=>import('@/views/RecommendationsView.vue')),
  simulate:defineAsyncComponent(()=>import('@/views/SimulationView.vue')),
  compare:defineAsyncComponent(()=>import('@/views/ScenariosView.vue')),
  adjust:defineAsyncComponent(()=>import('@/views/SimulationView.vue')),
  analysis:defineAsyncComponent(()=>import('@/views/RisksView.vue')),
  market:defineAsyncComponent(()=>import('@/views/CarbonMarketView.vue')),
  report:defineAsyncComponent(()=>import('@/views/ReportsView.vue')),
}
const current=computed(()=>components[stage.value as keyof typeof components]||components.baseline)
const steps=[
  {key:'data',label:'数据接入',desc:'确认园区数据源、采集状态、质量与示范数据标识'},
  {key:'accounting',label:'碳排放核算',desc:'按同一园区活动数据形成可追溯核算结果'},
  {key:'baseline',label:'当前基准状态',desc:'确认园区能耗、排放、设备和冻结基准版本'},
  {key:'target',label:'目标与约束',desc:'设置达峰年份、碳配额、能耗目标和预算'},
  {key:'recommend',label:'路径推荐',desc:'生成经济优先、减排优先和综合平衡路径'},
  {key:'simulate',label:'全过程仿真',desc:'调用能源平衡和各设备模型运行场景'},
  {key:'compare',label:'场景结果对比',desc:'比较排放、能耗、投资、成本和目标完成度'},
  {key:'adjust',label:'情景参数调整',desc:'调整电价、碳价、配额、绿证和措施参数'},
  {key:'analysis',label:'综合分析',desc:'汇总经济性、目标完成情况和实施风险'},
  {key:'market',label:'碳市场评估',desc:'分析碳配额、CCER、绿证及综合碳成本'},
  {key:'report',label:'报告输出',desc:'冻结本次结果快照并生成 DOCX/PDF 报告'},
]
async function select(key:string){stage.value=key;await router.replace({query:{...route.query,stage:key,site:sites.currentSite?.id}})}
watch(()=>route.query.stage,v=>{if(v)stage.value=String(v)})
onMounted(()=>sites.loadSites())
</script>
<template><section class="neutral-workbench"><PageHeader kicker="园区低碳路径推演" title="碳中和仿真工作台" description="从数据接入、统一核算到路径推荐、仿真、碳市场、风险与报告，在同一园区上下文中连续完成。"/><EmptyState v-if="!sites.currentSite" title="暂无园区" description="请先在园区管理中创建园区及基础对象"/><template v-else><div class="park-context"><span>当前园区</span><b>{{sites.currentSite.name}}</b><el-tag>数据按当前园区隔离</el-tag><el-tag type="warning">示范仿真数据</el-tag></div><nav class="flow-nav" aria-label="碳中和完整业务流程" data-testid="complete-carbon-flow"><button v-for="(item,index) in steps" :key="item.key" :class="{active:stage===item.key}" @click="select(item.key)"><i>{{index+1}}</i><span><b>{{item.label}}</b><small>{{item.desc}}</small></span></button></nav><el-alert v-if="stage==='adjust'" title="情景参数调整会形成临时配置或新场景版本，不覆盖历史不可变版本。" type="info" :closable="false"/><el-alert v-if="stage==='data'" title="真实设备不可用时保留示范仿真数据；真实数据接入后按统一字段逐步替换，不冒充实测数据。" type="info" :closable="false"/><div class="stage-content"><component :is="current"/></div></template></section></template>
<style scoped>.park-context{display:flex;align-items:center;gap:12px;padding:12px 16px;margin-bottom:14px;background:#eef7f4;border:1px solid #cfe4dd;border-radius:10px}.flow-nav{display:flex;gap:8px;margin-bottom:16px;overflow-x:auto;padding-bottom:5px;scrollbar-width:thin}.flow-nav button{display:flex;gap:9px;text-align:left;border:1px solid #d8e3df;border-radius:10px;background:#fff;padding:12px;min-height:82px;min-width:180px;flex:1 0 180px;cursor:pointer}.flow-nav button.active{border-color:#23876d;background:#edf8f4}.flow-nav i{display:grid;place-items:center;flex:none;width:24px;height:24px;border-radius:50%;background:#e1eee9;color:#176b57;font-style:normal}.flow-nav span{display:flex;flex-direction:column;gap:5px}.flow-nav small{color:#6e7f79;line-height:1.4}.stage-content{border-top:1px solid #e3ebe8;padding-top:8px}@media(max-width:1200px){.flow-nav button{min-width:165px;flex-basis:165px}}</style>
