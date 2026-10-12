<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import {useRoute,useRouter} from 'vue-router';
import {http,silentConfig} from '@/api/http';
import StatCard from '@/components/StatCard.vue';
import BaseChart from '@/components/BaseChart.vue';
import type {EChartsOption} from 'echarts';
type Row={id:number;building_id:string;name:string;energy_kwh:number;water_m3:number;gas_m3:number;grid_import_kwh:number;emission_t:number;scope1_t:number;scope2_t:number;trend:Array<{timestamp:string;emission_t:number}>};
type Snapshot={timestamp:string;data_notice:string;period_start:string;total_emission_t:number;buildings:Row[];trend:Row['trend'];factors:{electricity:{value:number;unit:string};natural_gas:{value:number;unit:string};source:string}};
const props=defineProps<{siteId:number}>(),route=useRoute(),router=useRouter();
const snapshot=ref<Snapshot>(),buildingId=ref<number>(),error=ref(''),loading=ref(false);
const selected=computed(()=>snapshot.value?.buildings.find(b=>b.id===buildingId.value));
const rows=computed(()=>selected.value?[selected.value]:snapshot.value?.buildings||[]);
const sum=(key:keyof Row)=>rows.value.reduce((n,b)=>n+Number(b[key]||0),0);
const total=computed(()=>sum('emission_t'));
const fmt=(v:number)=>v.toLocaleString('zh-CN',{maximumFractionDigits:2});
const trend=computed(()=>selected.value?.trend||snapshot.value?.trend||[]);
const option=computed<EChartsOption>(()=>({tooltip:{trigger:'axis'},xAxis:{type:'category',data:trend.value.map(p=>p.timestamp)},yAxis:{type:'value',name:'吨二氧化碳当量'},series:[{name:'碳排放',type:'line',data:trend.value.map(p=>p.emission_t),lineStyle:{color:'#288f7b'}}]}));
const activities=computed(()=>snapshot.value?[
 {name:'电网购电',value:sum('grid_import_kwh'),unit:'千瓦时',factor:snapshot.value.factors.electricity.value,factorUnit:'千克二氧化碳当量/千瓦时',emission:sum('scope2_t'),scope:'间接排放'},
 {name:'天然气',value:sum('gas_m3'),unit:'立方米',factor:snapshot.value.factors.natural_gas.value,factorUnit:'千克二氧化碳当量/立方米',emission:sum('scope1_t'),scope:'直接排放'}]:[]);
async function load(){loading.value=true;error.value='';try{
 const at=typeof route.query.at==='string'?route.query.at:undefined;
 snapshot.value=await http.get(`/api/result-interface/campuses/${props.siteId}/live-demo`,{...silentConfig,params:{at,history_hours:1}}) as unknown as Snapshot;
 buildingId.value=route.query.building?Number(route.query.building):undefined;
 if(buildingId.value&&!selected.value)error.value='该建筑不属于当前校园的示范业务绑定范围';
}catch(e){error.value=(e as {message?:string}).message||'统一校园核算快照加载失败'}finally{loading.value=false}}
function choose(id?:number){void router.replace({query:{...route.query,building:id}})}
watch(()=>[props.siteId,route.query.at,route.query.building],load,{immediate:true});
</script>
<template><section class="campus-accounting" data-testid="campus-snapshot-accounting" v-loading="loading">
 <el-alert v-if="error" :title="error" type="error" :closable="false"/>
 <template v-else-if="snapshot">
 <el-alert :title="`${snapshot.data_notice} · 与校园大屏共用同一核算快照`" type="info" :closable="false"/>
 <div class="toolbar"><el-select :model-value="buildingId" clearable placeholder="全校园汇总" @change="choose"><el-option v-for="b in snapshot.buildings" :key="b.id" :value="b.id" :label="b.name"/></el-select><el-button @click="load">重新读取当前快照</el-button><span>核算对象：{{selected?.name||'全校园'}}</span></div>
 <p>核算范围：{{snapshot.period_start}}至{{new Date(snapshot.timestamp).toLocaleString('zh-CN')}}。从大屏进入时保留同一截止时间，不切换为历史年度核算。</p>
 <div class="stat-grid"><StatCard label="总碳排放量" :value="total" unit="吨二氧化碳当量"/><StatCard label="直接排放" :value="sum('scope1_t')" unit="吨二氧化碳当量"/><StatCard label="间接排放" :value="sum('scope2_t')" unit="吨二氧化碳当量"/></div>
 <article class="panel"><h2>{{selected?.name||'全校园'}}碳排放趋势</h2><BaseChart :option="option" :empty="!trend.length"/></article>
 <article class="panel"><h2>能源活动与核算结果</h2><p>排放量＝活动量×排放因子÷1000。电力以电网购电量核算，不重复计入光伏自用减排；空调和照明已包含在建筑电量中。</p><el-table :data="activities"><el-table-column prop="name" label="能源"/><el-table-column label="活动量"><template #default="{row}">{{fmt(row.value)}} {{row.unit}}</template></el-table-column><el-table-column label="排放因子" min-width="220"><template #default="{row}">{{row.factor}} {{row.factorUnit}}</template></el-table-column><el-table-column prop="scope" label="核算边界"/><el-table-column label="碳排放"><template #default="{row}">{{fmt(row.emission)}} 吨</template></el-table-column></el-table><p>{{snapshot.factors.source}}。公共储能及光伏作用后的购电量按建筑需求比例分配，天然气归属于食堂。</p></article>
 <article class="panel"><h2>建筑级核算明细</h2><el-table :data="rows"><el-table-column prop="name" label="建筑"/><el-table-column prop="building_id" label="建筑编码"/><el-table-column label="累计用电"><template #default="{row}">{{fmt(row.energy_kwh)}} 千瓦时</template></el-table-column><el-table-column label="分配购电量"><template #default="{row}">{{fmt(row.grid_import_kwh)}} 千瓦时</template></el-table-column><el-table-column label="用水"><template #default="{row}">{{fmt(row.water_m3)}} 立方米</template></el-table-column><el-table-column label="碳排放"><template #default="{row}">{{fmt(row.emission_t)}} 吨</template></el-table-column></el-table><p>用水展示为资源统计，当前未配置用水排放因子，不计入碳排放。</p></article>
 </template>
</section></template>
<style scoped>.toolbar{display:flex;align-items:center;gap:16px;margin:18px 0}.panel{margin:18px 0;padding:20px}.campus-accounting p{color:#526b72;line-height:1.7}</style>
