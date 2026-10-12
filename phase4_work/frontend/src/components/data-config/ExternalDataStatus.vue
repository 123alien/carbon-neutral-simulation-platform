<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref} from 'vue';

type State={connected?:boolean;credentials_configured?:boolean;token_valid?:boolean;device_count?:number;online_count?:number;offline_count?:number;unmapped_count?:number;latest_metric_count?:number;property_count?:number;valid_value_count?:number;collected_at?:string;latest_observation_time?:string;collection_mode?:string;error?:string};
type Row={id:number;payload:Record<string,any>};
const states=ref<Record<string,State>>({});
const rows=ref<Row[]>([]);
const source=ref('IOT_CLOUD');
const kind=ref('DEVICE');
const error=ref('');
const busy=ref(false);
const sources=['IOT_CLOUD','WEATHER_STATION'];
const label=(s:string)=>s==='IOT_CLOUD'?'物联网云平台 · 室内环境设备':'气象站';

async function request(path:string,options?:RequestInit){
  const response=await fetch('/api/external-data/'+path,options);
  const data=await response.json();
  if(!response.ok)throw new Error(data.detail||'外部数据读取失败');
  return data;
}
async function refresh(){try{states.value=await request('status')}catch(e){error.value=(e as Error).message}}
async function view(){try{rows.value=await request(`records?source_type=${source.value}&kind=${kind.value}`)}catch(e){error.value=(e as Error).message}}
async function collect(s:string){
  busy.value=true;error.value='';
  try{
    await request('collect/'+s,{method:'POST'});
    source.value=s;kind.value=s==='IOT_CLOUD'?'DEVICE':'METRIC';
    await view();
  }catch(e){error.value=(e as Error).message}
  finally{await refresh();busy.value=false}
}
let refreshTimer:ReturnType<typeof setInterval>|undefined;
onMounted(()=>{
  void refresh();
  refreshTimer=setInterval(()=>{
    if(document.hidden||busy.value)return;
    void refresh();
    if(source.value==='IOT_CLOUD'&&kind.value==='METRIC')void view();
  },30000);
});
onBeforeUnmount(()=>{if(refreshTimer)clearInterval(refreshTimer)});
const quality=(s:string)=>({READY:'待人工映射',MISSING_VALUE:'上游未返回观测值',MISSING_TIMESTAMP:'缺少观测时间',UNIT_NOT_PROVIDED:'上游未提供单位'}[s]||s);
</script>

<template>
  <section class="external-status" data-testid="external-data-status">
    <h3>真实数据接入状态</h3>
    <router-link class="monitor-link" to="/device-monitor">查看设备实时曲线与离线列表 →</router-link>
    <p>物联网云平台通过后端 Token 接口自动采集室内设备，无需图形验证码。室内 CO₂ 浓度、温湿度仅用于环境监测，不直接参与建筑碳排核算。</p>
    <div class="source-cards">
      <article v-for="s in sources" :key="s">
        <b>{{label(s)}}</b><span>{{states[s]?.connected?'已连接':'未连接'}}</span>
        <template v-if="s==='IOT_CLOUD'">
          <p>鉴权：{{!states[s]?.credentials_configured?'未配置凭证':states[s]?.token_valid?'Token 有效':'尚未验证'}}</p>
          <p>采集方式：{{states[s]?.collection_mode==='AUTOMATIC_TOKEN_API_POLL'?'后台自动采集':'等待采集'}}</p>
          <p>真实设备 {{states[s]?.device_count??'未查询'}} · 在线 {{states[s]?.online_count??'未确认'}} · 离线 {{states[s]?.offline_count??'未确认'}}</p>
          <p>待绑定 {{states[s]?.unmapped_count??'未查询'}} · 最新指标 {{states[s]?.latest_metric_count??'未查询'}}</p>
          <p>最近观测：{{states[s]?.latest_observation_time??'尚未提供'}}</p>
        </template>
        <template v-else>
          <p>实际属性 {{states[s]?.property_count??'未查询'}} · 有效观测 {{states[s]?.valid_value_count??'未查询'}}</p>
          <p>观测更新时间：{{states[s]?.latest_observation_time??'上游尚未提供'}}</p>
        </template>
        <p>最近请求：{{states[s]?.collected_at??'尚未采集'}}</p>
        <p v-if="states[s]?.error" class="warning">{{states[s].error}}</p>
        <button :disabled="busy" @click="collect(s)">{{busy?'请求中…':'立即采集'}}</button>
      </article>
    </div>
    <p v-if="error" class="warning">{{error}}</p>
    <div class="actions">
      <select v-model="source"><option value="IOT_CLOUD">物联网云平台</option><option value="WEATHER_STATION">气象站</option></select>
      <select v-model="kind"><option value="DEVICE">设备与建筑映射</option><option value="METRIC">最新指标记录</option></select>
      <button @click="view">查看记录</button><button @click="refresh">刷新状态</button>
    </div>
    <div class="records">
      <table v-if="rows.length">
        <thead><tr><th>设备</th><th>指标 / 因子</th><th>数值</th><th>单位</th><th>观测时间</th><th>位置 / 状态</th></tr></thead>
        <tbody><tr v-for="r in rows" :key="r.id">
          <td>{{r.payload.device_name||r.payload.upstream_device_name||r.payload.device_id}}</td>
          <td>{{r.payload.metric_name||r.payload.raw_payload?.factors?.map((x:any)=>`${x.factorName}：${x.unit??'未提供单位'}`).join('；')||'上游未提供因子'}}</td>
          <td>{{r.payload.value??'暂无观测值'}}</td>
          <td>{{r.payload.unit??'上游未提供'}}</td>
          <td>{{r.payload.timestamp??'上游未提供'}}</td>
          <td>{{r.payload.building_id?`${r.payload.building_id} · ${r.payload.floor_id||'楼层未确认'} · 已人工确认`:r.payload.mapping_status?'待绑定建筑':quality(r.payload.quality_status)}}</td>
        </tr></tbody>
      </table>
      <p v-else>尚无查询记录，请选择数据源后采集或查看。</p>
    </div>
  </section>
</template>

<style scoped>
.external-status{background:white;border:1px solid #d8e5e5;border-radius:10px;padding:18px;margin:16px 0;color:#16414c}
.monitor-link{float:right;font-size:13px;color:#087f78;text-decoration:none}
.source-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.source-cards article{padding:14px;border:1px solid #dbe5e8;border-radius:8px}
.source-cards span{float:right}
.external-status p{font-size:12px;line-height:1.6}
.actions{display:flex;gap:8px;margin:12px 0;align-items:center}
.records{max-height:320px;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{text-align:left;border-bottom:1px solid #e2e9ea;padding:8px}
.warning{color:#a75b18}
button,select{padding:6px 10px;border:1px solid #b6d4d4;border-radius:4px;background:#f4fafa;color:#16414c}
@media(max-width:1000px){.source-cards{grid-template-columns:1fr}}
</style>
