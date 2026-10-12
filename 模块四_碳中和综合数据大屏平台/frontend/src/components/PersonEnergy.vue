<script setup lang="ts">
import {computed,ref,onMounted,onBeforeUnmount} from 'vue'
import Chart from './Chart.vue'

const emit=defineEmits<{summary:[value:{task_id:string;camera_count:number;track_count:number;max_people:number;sensor_count:number;online_sensors:number}]}>()

type Factor={metric_name:string;value:number|string|null;unit:string|null;timestamp:string|null;quality_status:string|null;points:{timestamp:string;value:number|string}[]}
type Sensor={device_id:string;device_name:string;online:boolean;building_id:string;floor_id:string;factors:Factor[]}
type Environment={source_type:string;location_notice:string;last_collected_at:string|null;collection_connected:boolean;devices:Sensor[]}
const tasks=ref<any[]>([]),task=ref('20260909_194141_0911e8'),data=ref<any>(),environment=ref<Environment>(),error=ref(''),sensorError=ref(''),busy=ref(false)
const selectedCamera=ref('cam1'),selectedSensor=ref(''),videoSecond=ref(0),videoError=ref('')
const sensorMetric=ref<'temperature'|'humidity'|'co2'>('temperature')
const playbackNotice=ref('')
const abort=new AbortController()
const fmt=(value:any)=>typeof value==='number'?value.toLocaleString('zh-CN',{maximumFractionDigits:4}):'未提供'
const camera=computed(()=>data.value?.cameras?.find((item:any)=>item.camera_id===selectedCamera.value)||data.value?.cameras?.[0])
const sensor=computed(()=>environment.value?.devices.find(item=>item.device_id===selectedSensor.value)||environment.value?.devices[0])
const peopleNow=computed(()=>{
 const points=camera.value?.people_timeline||[]
 let count:number|null=null
 for(const point of points){if(Number(point.second)>videoSecond.value)break;count=Number(point.people)}
 return count
})
function currentTime(event:Event){videoSecond.value=(event.target as HTMLVideoElement).currentTime}
async function autoplayVideo(event:Event){
 const player=event.target as HTMLVideoElement
 player.muted=true
 try{await player.play();playbackNotice.value=''}
 catch{playbackNotice.value='浏览器阻止了自动播放，请点击视频播放按钮。'}
}
function metric(code:string){return data.value?.metrics?.find((item:any)=>item.code===code)}
const energyComparable=computed(()=>typeof metric('energy_delta')?.value==='number'&&typeof metric('wasted_energy')?.value==='number')
function factor(kind:'temperature'|'humidity'|'co2'){
 const found=sensor.value?.factors.find(item=>{
  const name=item.metric_name?.toLowerCase()||'';const unit=item.unit?.toLowerCase()||''
  return kind==='temperature'?(unit==='℃'||name.includes('温度')):kind==='humidity'?(unit==='%'||name.includes('湿度')):(unit==='ppm'||name.includes('co2')||name.includes('二氧化碳'))
 })
 return found
}
async function load(){
 busy.value=true;error.value='';videoError.value='';playbackNotice.value='';videoSecond.value=0;data.value=undefined
 try{
  const response=await fetch(`/api/person-energy/tasks/${encodeURIComponent(task.value)}`,{signal:abort.signal})
  const result=await response.json();if(!response.ok)throw Error(result.detail)
  data.value=result;selectedCamera.value=result.cameras?.[0]?.camera_id||'cam1'
  emitSummary()
 }catch(e){if(!abort.signal.aborted)error.value=(e as Error).message}
 finally{busy.value=false}
}
async function loadEnvironment(){
 try{
  const response=await fetch('/api/person-energy/environment',{signal:abort.signal})
  const result=await response.json();if(!response.ok)throw Error(result.detail)
  environment.value=result;sensorError.value=''
  if(!selectedSensor.value)selectedSensor.value=result.devices?.[0]?.device_id||''
  emitSummary()
 }catch(e){if(!abort.signal.aborted)sensorError.value=(e as Error).message}
}
onMounted(async()=>{
 try{const response=await fetch('/api/activities/tasks',{signal:abort.signal});if(response.ok)tasks.value=await response.json()}catch{}
 if(!abort.signal.aborted){void load();void loadEnvironment()}
})
onBeforeUnmount(()=>abort.abort())
function occupancyOption(item:any){return {
 animation:false,grid:{left:43,right:14,top:25,bottom:30},
 tooltip:{trigger:'axis',backgroundColor:'#092c3d',borderColor:'#38aab5',textStyle:{color:'#e6fbff'}},
 xAxis:{type:'category',name:'相对秒',data:item.people_timeline.map((point:any)=>point.second),axisLabel:{color:'#8eb7bf',fontSize:10},axisLine:{lineStyle:{color:'#3b7381'}}},
 yAxis:{type:'value',name:'画面人数',minInterval:1,axisLabel:{color:'#8eb7bf',fontSize:10},splitLine:{lineStyle:{color:'rgba(115,190,199,.16)'}}},
 series:[{name:'画面人数',type:'line',step:'end',data:item.people_timeline.map((point:any)=>point.people),lineStyle:{color:'#59e6d4',width:2},areaStyle:{color:'rgba(56,210,198,.13)'},showSymbol:false}]
}}
function energyOption(){return {
 animation:false,grid:{left:113,right:30,top:16,bottom:28},
 tooltip:{trigger:'axis',axisPointer:{type:'shadow'},backgroundColor:'#092c3d',borderColor:'#38aab5',textStyle:{color:'#e6fbff'}},
 xAxis:{type:'value',name:'kWh',axisLabel:{color:'#8eb7bf',fontSize:10},splitLine:{lineStyle:{color:'rgba(115,190,199,.16)'}}},
 yAxis:{type:'category',data:['空置浪费估计','区间耗电增量'],axisLabel:{color:'#b9d8dc',fontSize:11},axisLine:{show:false},axisTick:{show:false}},
 series:[{name:'已有报告结果',type:'bar',barWidth:16,data:[{value:metric('wasted_energy')?.value,itemStyle:{color:'#dfaf61'}},{value:metric('energy_delta')?.value,itemStyle:{color:'#43cec1'}}],label:{show:true,position:'right',color:'#e4fbf7',formatter:'{c} kWh'}}]
}}
function sensorOption(){const points=factor(sensorMetric.value)?.points||[];const name=sensorMetric.value==='temperature'?'温度':sensorMetric.value==='humidity'?'湿度':'二氧化碳';const unit=factor(sensorMetric.value)?.unit||'';return {
 animation:false,grid:{left:49,right:16,top:27,bottom:35},
 tooltip:{trigger:'axis',backgroundColor:'#092c3d',borderColor:'#38aab5',textStyle:{color:'#e6fbff'}},
 xAxis:{type:'time',axisLabel:{color:'#8eb7bf',fontSize:10,formatter:'{HH}:{mm}'},axisLine:{lineStyle:{color:'#3b7381'}}},
 yAxis:{type:'value',name:unit,scale:true,nameTextStyle:{color:'#8eb7bf'},axisLabel:{color:'#8eb7bf',fontSize:10},splitLine:{lineStyle:{color:'rgba(115,190,199,.16)'}}},
 series:[{name:`${name} (${unit})`,type:'line',showSymbol:false,data:points.map(point=>[point.timestamp,Number(point.value)]).filter(item=>Number.isFinite(item[1] as number)),lineStyle:{color:'#5ae0cf',width:2},areaStyle:{color:'rgba(47,192,180,.14)'}}]
}}
function emitSummary(){
 const cameras=data.value?.cameras||[],devices=environment.value?.devices||[]
 emit('summary',{task_id:task.value,camera_count:cameras.length,track_count:cameras.reduce((sum:number,item:any)=>sum+Number(item.track_count||0),0),max_people:Math.max(0,...cameras.map((item:any)=>Number(item.max_people||0))),sensor_count:devices.length,online_sensors:devices.filter((item:Sensor)=>item.online).length})
}
</script>

<template>
 <section class="person-energy" data-testid="person-energy">
  <div class="analysis-head"><div><span class="eyebrow">VIDEO × ENERGY</span><h2>人员碳能耗</h2></div><div class="task-controls"><select v-model="task" aria-label="人员能耗任务"><option v-for="item in tasks" :key="item.task_id" :value="item.task_id">{{item.task_id}}</option></select><button :disabled="busy" @click="load">{{busy?'读取中…':'读取结果'}}</button></div></div>
  <p v-if="error" class="alert" role="alert">{{error}}</p>
  <p v-if="data?.status==='NO_REPORT'" class="alert">该任务尚无能耗关联报告。仍展示已有视频与人数结果；不以 0 冒充缺失能耗。</p>
  <div class="analysis-grid">
   <div class="video-column">
    <article class="visual-card"><header><div><span class="eyebrow">RECOGNITION</span><h3>{{selectedCamera}} · 识别视频</h3></div><span class="status-tag">任务录像</span></header>
     <div class="camera-tabs"><button v-for="item in data?.cameras" :key="item.camera_id" :class="{active:selectedCamera===item.camera_id}" @click="selectedCamera=item.camera_id;videoSecond=0;videoError='';playbackNotice=''">{{item.camera_id}}</button></div>
     <div class="video-frame"><video v-if="camera" :key="`${task}-${selectedCamera}`" :src="`/api/videos/tasks/${encodeURIComponent(task)}/${encodeURIComponent(selectedCamera)}`" controls autoplay muted playsinline preload="auto" @canplay="autoplayVideo" @timeupdate="currentTime" @error="videoError='该任务录像暂不可用或浏览器无法解码'"/><div v-else class="video-placeholder">请选择真实任务读取视频</div><div v-if="camera&&peopleNow!==null" class="people-badge"><small>画面人数</small><strong>{{peopleNow}}</strong><small>视频 {{videoSecond.toFixed(1)}} 秒</small></div></div>
     <p v-if="playbackNotice" class="playback-notice">{{playbackNotice}}</p>
     <p v-if="videoError" class="video-error">{{videoError}}</p>
     <div class="video-facts"><div><small>本镜轨迹数</small><b>{{fmt(camera?.track_count)}}</b></div><div><small>最多同框人数</small><b>{{fmt(camera?.max_people)}}</b></div><div><small>首次出现</small><b>{{fmt(camera?.first_person_seconds)}} 秒</b></div><div><small>最后出现</small><b>{{fmt(camera?.last_person_seconds)}} 秒</b></div></div>
    </article>
    <article class="visual-card occupancy-card"><header><div><span class="eyebrow">OCCUPANCY</span><h3>人数变化</h3></div><small>有人 {{fmt(camera?.occupied_seconds)}}s · 无人 {{fmt(camera?.empty_seconds)}}s</small></header><div v-if="camera?.people_timeline?.length" class="occupancy-chart"><Chart :option="occupancyOption(camera)"/></div><p v-else class="empty">暂无逐秒人数</p></article>
   </div>
   <div class="results-column">
    <article class="visual-card"><header><div><span class="eyebrow">ACCOUNTING RESULT</span><h3>能耗与碳排放</h3></div><span class="status-tag amber">{{data?.report?'已有上游报告':'暂无报告'}}</span></header>
     <div class="metric-grid"><div v-for="item in data?.metrics" :key="item.code" :class="item.code"><small>{{item.name}}</small><b>{{fmt(item.value)}}</b><span>{{item.unit}}</span></div><div v-if="!data?.metrics?.length" class="empty">上游尚无可核验的能耗指标。</div></div>
     <div class="comparison-heading"><b>用电对比</b><small>kWh</small></div>
     <div v-if="energyComparable" class="energy-chart"><Chart :option="energyOption()"/></div><p v-else class="empty">上游未提供可比较的区间用电和空置浪费估计。</p>
    </article>
    <article class="visual-card environment-card"><header><div><span class="eyebrow">OBSERVED ENVIRONMENT</span><h3>室内环境监测</h3></div><button @click="loadEnvironment">刷新实测</button></header>
     <p v-if="sensorError" class="alert">{{sensorError}}</p>
     <div class="sensor-controls"><span>{{environment?.collection_connected?'物联网云平台 · 已连接':'物联网云平台 · 状态待确认'}}</span><select v-model="selectedSensor" aria-label="环境设备"><option v-for="item in environment?.devices" :key="item.device_id" :value="item.device_id">设备 {{item.device_id}}</option></select></div>
     <div class="sensor-values"><div v-for="kind in (['temperature','humidity','co2'] as const)" :key="kind"><small>{{kind==='temperature'?'温度':kind==='humidity'?'湿度':'二氧化碳'}}</small><b>{{fmt(factor(kind)?.value)}} <i>{{factor(kind)?.unit||''}}</i></b></div></div>
     <div class="sensor-trend-head"><b>最近一小时实测波动</b><div><button v-for="kind in (['temperature','humidity','co2'] as const)" :key="kind" :class="{active:sensorMetric===kind}" @click="sensorMetric=kind">{{kind==='temperature'?'温度':kind==='humidity'?'湿度':'CO₂'}}</button></div></div>
     <div v-if="(factor(sensorMetric)?.points?.length||0)>1" class="sensor-chart"><Chart :option="sensorOption()"/></div><p v-else class="empty">该设备当前采样点不足，暂不绘制趋势。</p>
     <div class="sensor-list"><button v-for="item in environment?.devices" :key="item.device_id" :class="{active:selectedSensor===item.device_id}" @click="selectedSensor=item.device_id"><span :class="{offline:!item.online}"></span>{{item.device_id}} <small>{{item.online?'在线':'离线/未知'}}</small></button></div>
     <p class="footnote">香帅楼10楼实测 · {{environment?.last_collected_at||'未提供'}}</p>
    </article>
   </div>
  </div>
  <details v-if="data" class="details"><summary>数据说明与溯源</summary><p>任务录像非实时监控；传感器未证实与视频同房间；当前无 Global ID 个人能耗分摊，不与校园年度核算相加。</p><pre>{{JSON.stringify(data.raw_payload,null,2)}}</pre></details>
 </section>
</template>

<style scoped>
.person-energy{color:#e7f9f9}.eyebrow{display:block;font-size:10px;letter-spacing:1.7px;color:#67dcd8;font-weight:700}.analysis-head{display:flex;justify-content:space-between;align-items:end;gap:16px;margin-bottom:12px}.analysis-head h2{font-size:22px;margin:4px 0}.analysis-head p{font-size:11px;color:#9fc2c9;margin:0}.task-controls{display:flex;gap:8px}.task-controls select,.task-controls button,.environment-card button,.environment-card select{padding:8px 10px;border:1px solid #348296;background:#0b394a;color:#e6ffff;border-radius:3px}.task-controls button{background:#087e87;font-weight:700}.task-controls select{min-width:210px}.analysis-grid{display:grid;grid-template-columns:minmax(0,1.03fr) minmax(0,1fr);gap:12px}.video-column,.results-column{display:flex;flex-direction:column;gap:12px;min-width:0}.visual-card{background:linear-gradient(155deg,#10394a,#0a2a39);border:1px solid #2f6d7e;padding:12px;min-width:0;box-shadow:inset 0 1px rgba(122,224,227,.1)}.visual-card header{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px}.visual-card h3{font-size:16px;margin:3px 0}.visual-card header>small{color:#92b6bf}.status-tag{font-size:10px;border:1px solid #367f88;color:#6ce3d5;background:#124452;padding:5px 7px;white-space:nowrap}.status-tag.amber{color:#e8ca85;border-color:#907348;background:#3f3828}.camera-tabs{display:flex;gap:5px;margin-bottom:8px}.camera-tabs button{padding:5px 13px;border:1px solid #2f7280;background:#092d3d;color:#9bc4c8}.camera-tabs button.active{background:#0a7c85;color:white;border-color:#4cdbd3}.video-frame{position:relative;background:#020c12;aspect-ratio:16/9}.video-frame video{width:100%;height:100%;display:block;object-fit:contain}.video-placeholder{height:100%;display:grid;place-items:center;color:#86acb6}.people-badge{position:absolute;top:10px;right:10px;padding:8px 11px;background:rgba(4,34,39,.87);border:1px solid #4c9d9d;pointer-events:none}.people-badge small,.people-badge strong{display:block}.people-badge small{font-size:10px;color:#b9d7d9}.people-badge strong{font-size:24px;color:#b7f55a;line-height:1.1}.video-error{color:#ffc1ac;font-size:11px}.video-facts{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#2c6571;margin-top:9px}.video-facts div{background:#0d3544;padding:9px}.video-facts small,.video-facts b{display:block}.video-facts small{font-size:10px;color:#96b8c1}.video-facts b{font-size:14px;margin-top:4px;color:#ccf9ee}.occupancy-chart{height:154px;display:flex;min-width:0}.footnote{font-size:10px;line-height:1.45;color:#8fb1bb;margin:8px 0 0}.source-warning{font-size:10px;line-height:1.5;color:#abc7ca;margin:0 0 10px}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.metric-grid>div{min-height:78px;border:1px solid #326a78;background:#0b3040;padding:10px}.metric-grid>div.wasted_carbon{border-color:#549774;background:#173d3d}.metric-grid>div.wasted_energy{border-color:#80744b;background:#343726}.metric-grid small,.metric-grid b,.metric-grid span{display:block}.metric-grid small{font-size:10px;color:#afc9cb}.metric-grid b{font-size:23px;margin-top:5px;color:#eefef8;font-variant-numeric:tabular-nums}.metric-grid span{font-size:10px;color:#a4c4c7}.time-series-note{margin-top:10px;padding:10px;border:1px dashed #507683;color:#a9c8ce;font-size:11px}.time-series-note b{color:#e6f7f9}.time-series-note p{margin:5px 0 0}.sensor-controls{display:flex;justify-content:space-between;gap:8px;align-items:center;font-size:10px;color:#75dace}.sensor-controls select{padding:5px 8px;max-width:160px}.sensor-values{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}.sensor-values div{padding:10px;background:#0b3442;border:1px solid #316b75}.sensor-values small,.sensor-values b{display:block}.sensor-values small{font-size:10px;color:#a4c2c7}.sensor-values b{font-size:20px;margin-top:5px}.sensor-values i{font-size:10px;font-style:normal;color:#9db9bf}.sensor-list{display:grid;grid-template-columns:1fr 1fr;gap:6px}.sensor-list button{display:flex;align-items:center;gap:5px;text-align:left;padding:7px;font-size:11px}.sensor-list button.active{border-color:#67ded6;background:#124b54}.sensor-list button span{width:6px;height:6px;background:#4bd2a9;border-radius:50%}.sensor-list button span.offline{background:#d48667}.sensor-list small{margin-left:auto;color:#a7c6c9;font-size:10px}.details{margin-top:9px;padding:9px 11px;background:#0b3040;border:1px solid #2e6878;font-size:11px;color:#b5d2d8}.details summary{cursor:pointer;color:#71dad6}.details pre{max-height:180px;overflow:auto}.boundary,.alert{font-size:11px;color:#d6c39a;padding:9px 11px;background:#393629;border-left:2px solid #d9a94c;margin:10px 0}.empty{color:#93bac4;font-size:11px}.alert{color:#ffcfbf;background:#432e31;border-color:#d18066}@media(max-width:1100px){.analysis-grid{grid-template-columns:1fr}}@media(max-width:680px){.analysis-head{flex-direction:column;align-items:start}.task-controls{width:100%}.task-controls select{min-width:0;flex:1}.video-facts{grid-template-columns:repeat(2,1fr)}}
.comparison-heading,.sensor-trend-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:12px;color:#dff6f6;font-size:11px}
.comparison-heading small{color:#8eafba;font-size:10px}
.energy-chart{height:142px;display:flex;min-width:0;border:1px solid #315e6d;background:#092d3b;margin-top:6px}
.sensor-trend-head>div{display:flex;gap:4px}
.sensor-trend-head button{padding:4px 7px;font-size:10px;background:#092f3e;border:1px solid #3a7480;color:#a7ced1}
.sensor-trend-head button.active{background:#0d7a80;border-color:#56d6cf;color:#fff}
.sensor-chart{height:145px;display:flex;min-width:0;border:1px solid #315e6d;background:#092d3b;margin-top:6px}
.playback-notice{color:#8fd5cf;font-size:10px;margin:6px 0}
</style>
