<script setup lang="ts">
import {computed,onBeforeUnmount,onMounted,ref} from 'vue';
import type {EChartsOption} from 'echarts';
import BaseChart from '@/components/BaseChart.vue';

type Point={timestamp:string;value:number|string};
type Factor={metric_code:string;metric_name:string;unit:string|null;value:number|string|null;timestamp:string|null;points:Point[]};
type Device={device_id:string;device_name:string;device_status:string;online:boolean;building_id:string|null;floor_id:string|null;device_type?:string;factors:Factor[]};
type Dashboard={device_count:number;online_count:number;offline_count:number;unknown_count:number;last_collected_at:string|null;devices:Device[]};
const data=ref<Dashboard|null>(null);
const error=ref('');
const loading=ref(false);
const hours=ref(1);
const onlineDevices=computed(()=>data.value?.devices.filter(device=>device.online)??[]);
const offlineDevices=computed(()=>data.value?.devices.filter(device=>!device.online)??[]);
const colors=['#1bbdb1','#5a8fee','#efad46'];

async function refresh(){
  if(loading.value)return;
  loading.value=true;
  try{
    const response=await fetch(`/api/external-data/device-dashboard?hours=${hours.value}`);
    if(!response.ok)throw new Error('设备展示数据暂时不可用');
    const environment:Dashboard=await response.json();
    try{
      const meter=await loadEnergyMeters();
      data.value={device_count:environment.device_count+meter.device_count,online_count:environment.online_count+meter.online_count,offline_count:environment.offline_count+meter.offline_count,unknown_count:(environment.unknown_count||0)+(meter.unknown_count||0),last_collected_at:latestTime(environment.last_collected_at,meter.last_collected_at),devices:[...environment.devices,...meter.devices]};
      error.value='';
    }catch{data.value=environment;error.value='电表实时数据暂时不可用，环境监测数据已正常显示'}
  }catch(e){error.value=(e as Error).message}
  finally{loading.value=false}
}
async function fetchJson(url:string){const response=await fetch(url);if(!response.ok)throw new Error('request failed');return response.json()}
function utcTimestamp(value:string){return /(?:Z|[+-]\d\d:\d\d)$/.test(value)?value:`${value}Z`}
function timestampMs(value:string){return new Date(utcTimestamp(value)).getTime()}
async function loadEnergyMeters():Promise<Dashboard>{
  const sources=await fetchJson('/api/data-sources?enterprise_id=11');
  const source=[...sources].reverse().find((item:any)=>item.source_type==='MQTT'&&item.name==='能源管控电表 MQTT 实时数据');
  if(!source)return {device_count:0,online_count:0,offline_count:0,unknown_count:0,last_collected_at:null,devices:[]};
  const [runtime,devices]=await Promise.all([fetchJson(`/api/data-sources/${source.id}/runtime`),fetchJson(`/api/devices?enterprise_id=11&data_source_id=${source.id}`)]);
  const fresh=runtime.last_message_at&&Date.now()-timestampMs(runtime.last_message_at)<=180000;
  const online=Boolean(runtime.connected&&runtime.subscribed&&fresh);
  const labels:Record<string,string>={phase_a_voltage_v:'A相电压',phase_b_voltage_v:'B相电压',phase_c_voltage_v:'C相电压',phase_a_current_a:'A相电流',phase_b_current_a:'B相电流',phase_c_current_a:'C相电流',power_kw:'实时功率',energy_kwh:'累计电量',water_m3:'累计水量',temperature_c:'温度',humidity_pct:'湿度'};
  const cutoff=Date.now()-hours.value*3600000;
  const rows:Device[]=await Promise.all(devices.map(async(device:any)=>{
    const metrics=await fetchJson(`/api/devices/${device.id}/metrics`);
    const grouped=new Map<string,any[]>();
    for(const row of metrics){if(timestampMs(row.timestamp)<cutoff)continue;const list=grouped.get(row.metric_name)||[];list.push(row);grouped.set(row.metric_name,list)}
    const factors=[...grouped.entries()].map(([code,list])=>{const latest=list[list.length-1];return {metric_code:code,metric_name:labels[code]||code,unit:latest.unit,value:latest.value,timestamp:utcTimestamp(latest.timestamp),points:list.slice(-60).map(row=>({timestamp:utcTimestamp(row.timestamp),value:row.value}))}});
    return {device_id:device.external_id,device_name:device.name,device_status:online?'online':'offline',online,building_id:device.metadata_json?.building_id||null,floor_id:device.metadata_json?.floor_id||null,device_type:device.device_type,factors};
  }));
  return {device_count:rows.length,online_count:online?rows.length:0,offline_count:online?0:rows.length,unknown_count:0,last_collected_at:runtime.last_message_at,devices:rows};
}
function latestTime(...values:(string|null)[]){return values.filter(Boolean).sort().at(-1)||null}
function factorKey(factor:Factor){
  const name=factor.metric_name.toLowerCase();
  if(factor.unit==='℃'||name.includes('温度'))return 'temperature';
  if(factor.unit==='%'||name.includes('湿度'))return 'humidity';
  if(factor.unit?.toLowerCase()==='ppm'||name.includes('co2')||name.includes('二氧化碳'))return 'co2';
  return factor.metric_code;
}
function orderedFactors(device:Device){
  const order=isMeter(device)?['power_kw','energy_kwh','phase_a_voltage_v','phase_b_voltage_v','phase_c_voltage_v','phase_a_current_a','phase_b_current_a','phase_c_current_a']:['temperature','humidity','co2'];
  const rank=(factor:Factor)=>{const index=order.indexOf(factorKey(factor));return index<0?999:index};
  return [...device.factors].sort((a,b)=>rank(a)-rank(b));
}
function isMeter(device:Device){return device.device_type==='ELECTRIC_METER'}
function meterFactors(device:Device,prefix:string){return device.factors.filter(factor=>factor.metric_code.startsWith(prefix)).sort((a,b)=>a.metric_code.localeCompare(b.metric_code))}
function chartOption(device:Device,factorList?:Factor[]):EChartsOption{
  const factors=factorList||orderedFactors(device).slice(0,3);
  return {
    color:colors,
    animation:false,
    grid:{left:60,right:104,top:52,bottom:48},
    legend:{top:5,textStyle:{color:'#52737d',fontSize:11}},
    tooltip:{trigger:'axis',axisPointer:{type:'cross',label:{backgroundColor:'#426c75'}},confine:true},
    xAxis:{type:'time',name:'时间',nameLocation:'end',nameTextStyle:{color:'#69858d'},axisLabel:{color:'#69858d',fontSize:10,formatter:'{HH}:{mm}'},axisLine:{lineStyle:{color:'#b5ced0'}},splitLine:{show:false}},
    yAxis:factors.map((factor,index)=>({type:'value' as const,name:`${factor.metric_name} (${factor.unit||'—'})`,position:index===0?'left' as const:'right' as const,offset:index===2?52:0,scale:true,nameTextStyle:{color:colors[index],fontSize:10},axisLabel:{color:colors[index],fontSize:10},axisLine:{show:true,lineStyle:{color:colors[index]}},splitLine:{show:index===0,lineStyle:{color:'#e8f0f0'}}})),
    series:factors.map((factor,index)=>({name:`${factor.metric_name} (${factor.unit||'—'})`,type:'line' as const,yAxisIndex:index,showSymbol:false,symbolSize:5,lineStyle:{width:2},data:factor.points.map(point=>[point.timestamp,Number(point.value)]).filter(point=>Number.isFinite(point[1] as number))})),
  };
}
function displayValue(value:number|string|null){
  if(value===null||value===undefined)return '暂无';
  const number=Number(value);
  return Number.isFinite(number)?number.toLocaleString('zh-CN',{maximumFractionDigits:1}):value;
}
function displayTime(value:string|null){
  if(!value)return '暂无';
  const date=new Date(utcTimestamp(value));
  return Number.isNaN(date.getTime())?value:date.toLocaleString('zh-CN',{hour12:false});
}
let timer:ReturnType<typeof setInterval>|undefined;
onMounted(()=>{void refresh();timer=setInterval(()=>{if(!document.hidden)void refresh()},30000)});
onBeforeUnmount(()=>{if(timer)clearInterval(timer)});
</script>

<template>
  <section class="live-devices" data-testid="live-device-dashboard">
    <header class="section-head">
      <div><span class="eyebrow">IOT + ENERGY MQTT · REALTIME</span><h3>实时设备监测</h3><p>环境传感器与能源管控电表真实采集；曲线不以模拟值补点。</p></div>
      <div class="toolbar"><select v-model.number="hours" aria-label="趋势时间范围" @change="refresh"><option :value="1">近 1 小时</option><option :value="6">近 6 小时</option><option :value="24">近 24 小时</option></select><button :disabled="loading" @click="refresh">{{loading?'刷新中…':'刷新设备'}}</button></div>
    </header>
    <div class="summary">
      <div><span>设备总数</span><strong>{{data?.device_count??'—'}}</strong></div>
      <div><span>在线设备</span><strong class="online-text">{{data?.online_count??'—'}}</strong></div>
      <div><span>离线设备</span><strong class="offline-text">{{data?.offline_count??'—'}}</strong></div>
      <div><span>状态未知</span><strong>{{data?.unknown_count??'—'}}</strong></div>
      <div class="collected"><span>最近采集</span><strong>{{displayTime(data?.last_collected_at??null)}}</strong></div>
    </div>
    <p v-if="error" class="error">{{error}}；保留上次成功读取的画面，不代表当前设备在线。</p>
    <div v-if="onlineDevices.length" class="device-grid">
      <article v-for="device in onlineDevices" :key="device.device_id" class="device-card" :class="{'meter-card':isMeter(device)}">
        <header><div><b>{{device.device_name}}</b><small>{{device.device_id}} · {{device.building_id||'建筑未绑定'}} {{device.floor_id||''}}</small></div><span class="pill online">在线</span></header>
        <div v-if="device.factors.length" class="device-content">
          <div class="readouts" :class="{'meter-readouts':isMeter(device)}"><div v-for="(factor,index) in orderedFactors(device).slice(0,isMeter(device)?8:3)" :key="factor.metric_code" class="readout" :style="{'--line-color':colors[index%colors.length]}"><span>{{factor.metric_name}}</span><strong>{{displayValue(factor.value)}} <small>{{factor.unit||'单位未提供'}}</small></strong></div></div>
          <template v-if="isMeter(device)"><div class="meter-charts"><div><h4>三相电压</h4><BaseChart :option="chartOption(device,meterFactors(device,'phase_').filter(f=>f.metric_code.includes('voltage')))" height="230px" /></div><div><h4>三相电流</h4><BaseChart :option="chartOption(device,meterFactors(device,'phase_').filter(f=>f.metric_code.includes('current')))" height="230px" /></div><div><h4>功率与累计电量</h4><BaseChart :option="chartOption(device,device.factors.filter(f=>['power_kw','energy_kwh'].includes(f.metric_code)))" height="230px" /></div></div><p class="chart-caption">能源管控 MQTT 实测 · 横轴为接收时间；悬停查看三相电参量、功率及累计电量。</p></template>
          <template v-else><BaseChart :option="chartOption(device)" :empty="device.factors.every(factor=>!factor.points.length)" height="230px" /><p class="chart-caption">横轴：采样时间 · 纵轴：温度（℃）、湿度（%）、CO₂（ppm）分别按自身刻度显示。悬停曲线查看实际采样时间和值。</p></template>
        </div>
        <p v-else class="no-series">设备在线，尚无可展示的指标。</p>
      </article>
    </div>
    <p v-else class="empty">暂无在线设备。</p>
    <div class="offline-section"><h4>离线与状态未知设备 <span>{{offlineDevices.length}}</span></h4><p v-if="!offlineDevices.length">当前无离线或状态未知设备。</p><div v-else class="offline-list"><div v-for="device in offlineDevices" :key="device.device_id"><span class="pill offline">{{device.device_status==='unknown'?'状态未知':'离线'}}</span><b>{{device.device_name}}</b><small>{{device.device_id}} · {{device.building_id||'建筑未绑定'}}</small></div></div></div>
  </section>
</template>

<style scoped>
.live-devices{background:#fff;border:1px solid #d8e5e5;border-radius:10px;padding:20px;margin:16px 0;color:#16414c}
.section-head,.device-card header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.section-head h3{margin:4px 0 2px;font-size:20px}.section-head p{font-size:12px;margin:0;color:#66828b}.eyebrow{font-size:10px;letter-spacing:2px;color:#008f86;font-weight:700}
.toolbar{display:flex;gap:8px;flex-shrink:0}.toolbar select,.toolbar button{padding:7px 10px;background:#f4fafa;border:1px solid #b6d4d4;border-radius:5px;color:#16414c}
.summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr)) 1.7fr;gap:10px;margin:18px 0}.summary>div{border:1px solid #dceaea;background:#f6fbfa;border-radius:7px;padding:11px 14px;min-width:0}.summary span,.summary strong{display:block}.summary span{font-size:12px;color:#69858d}.summary strong{font-size:22px;margin-top:5px}.summary .collected strong{font-size:13px;margin-top:10px}.online-text{color:#139b7e}.offline-text{color:#d66b54}
.device-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.device-card{border:1px solid #cfe2e1;border-radius:8px;overflow:hidden;background:#fff}.device-card header{padding:12px 15px;background:#f2f9f8;border-bottom:1px solid #d9e9e7}.device-card header b,.device-card header small{display:block}.device-card header small{font-size:11px;color:#6b8790;margin-top:3px}.pill{font-size:11px;padding:3px 8px;border-radius:20px;white-space:nowrap}.pill.online{background:#daf7eb;color:#09875f}.pill.offline{background:#fff0e8;color:#b5593b}
.meter-card{grid-column:1/-1}.meter-card header{background:linear-gradient(90deg,#edf9f7,#f7fbff)}.meter-readouts{grid-template-columns:repeat(4,minmax(0,1fr))}.meter-charts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:8px}.meter-charts>div{border:1px solid #e0eceb;border-radius:6px;padding:6px;min-width:0}.meter-charts h4{font-size:12px;margin:2px 8px;color:#315f69}
.device-content{padding:8px 12px 10px}.readouts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.readout{border-left:3px solid var(--line-color);padding:4px 9px}.readout span,.readout strong{display:block}.readout span{font-size:11px;color:#61808a}.readout strong{font-size:18px;margin-top:3px}.readout strong small{font-size:10px;font-weight:400;color:#789097}.chart-caption{font-size:10px;color:#81989b;margin:0 2px 2px}.no-series,.empty{font-size:12px;color:#82989c;padding:15px}.offline-section{border-top:1px solid #e0ebea;margin-top:18px;padding-top:13px}.offline-section h4{font-size:14px;margin:0 0 10px}.offline-section h4 span{color:#9aadaf}.offline-section>p{font-size:12px;color:#81989b}.offline-list{display:flex;flex-wrap:wrap;gap:8px}.offline-list>div{display:flex;align-items:center;gap:8px;border:1px solid #edddda;border-radius:6px;padding:8px 10px}.offline-list small{font-size:11px;color:#7a8e95}.error{font-size:12px;color:#aa582d}
@media(max-width:1200px){.meter-charts{grid-template-columns:1fr}.meter-readouts{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:1100px){.summary{grid-template-columns:repeat(3,minmax(0,1fr))}.device-grid{grid-template-columns:1fr}}@media(max-width:650px){.section-head{flex-direction:column}.summary{grid-template-columns:repeat(2,minmax(0,1fr))}.readouts,.meter-readouts{grid-template-columns:1fr}}
</style>
