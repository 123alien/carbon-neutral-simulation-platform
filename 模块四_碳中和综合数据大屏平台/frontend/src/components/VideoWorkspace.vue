<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount,nextTick} from 'vue'
import type {ActivityPath} from '../types'
import PersonEnergy from './PersonEnergy.vue'

const emit=defineEmits<{summary:[value:{task_id:string;camera_count:number;track_count:number;max_people:number;sensor_count:number;online_sensors:number}]}>()

const tasks=ref<{task_id:string;status:string}[]>([]),task=ref(''),activeTask=ref(''),error=ref(''),busy=ref(false),paths=ref<ActivityPath[]>([]),selected=ref(''),playbackNotice=ref('')
const section=ref<'tracking'|'energy'>('tracking')
const players=ref<HTMLVideoElement[]>([])
function playerRef(element:unknown){if(element instanceof HTMLVideoElement&&!players.value.includes(element))players.value.push(element)}
async function startPlayback(){
 await nextTick()
 const results=await Promise.allSettled(players.value.map(async player=>{player.muted=true;await player.play()}))
 playbackNotice.value=results.some(result=>result.status==='rejected')?'浏览器阻止了自动播放，请点视频上的播放按钮。':'两路任务录像已静音自动播放，可在播放器中开启声音。'
}
const abort=new AbortController()
async function discover(){
 busy.value=true;error.value=''
 try{
  const response=await fetch('/api/activities/tasks',{signal:abort.signal});const result=await response.json()
  if(!response.ok)throw Error(result.detail||'读取任务失败')
  tasks.value=result;if(!task.value)task.value=result.find((item:any)=>item.status==='finished')?.task_id||''
  emit('summary',{task_id:task.value||'—',camera_count:2,track_count:0,max_people:0,sensor_count:0,online_sensors:0})
 }catch(e){if(!abort.signal.aborted)error.value=(e as Error).message}
 finally{busy.value=false}
}
async function load(){
 if(!task.value)return
 busy.value=true;error.value='';playbackNotice.value='';paths.value=[];selected.value='';players.value=[];activeTask.value=task.value
 void startPlayback()
 try{
  const response=await fetch('/api/activities/paths',{method:'POST',headers:{'Content-Type':'application/json'},signal:abort.signal,body:JSON.stringify({source:'LIVE',task_id:activeTask.value})})
  const result=await response.json();if(!response.ok)throw Error(result.detail||'关联结果读取失败');paths.value=result.paths
 }catch(e){if(!abort.signal.aborted)error.value=(e as Error).message}
 finally{busy.value=false}
}
onMounted(discover);onBeforeUnmount(()=>abort.abort())
</script>

<template>
 <section class="video-workspace panel" data-testid="video-workspace">
  <nav class="video-sections" aria-label="视频分析模块">
   <button :class="{active:section==='tracking'}" @click="section='tracking'"><span>01</span><b>跨镜目标检测</b><small>双路录像与匹配结果</small></button>
   <button :class="{active:section==='energy'}" @click="section='energy'"><span>02</span><b>人员碳能耗</b><small>占用、能耗与环境实测</small></button>
  </nav>
  <div v-if="section==='energy'" class="analysis-view"><PersonEnergy @summary="emit('summary',$event)"/></div>
  <section v-else class="cross-camera-section">
   <div class="video-toolbar"><div><span class="eyebrow">RECORDED TASK / NOT LIVE STREAM</span><h3>跨镜目标检测 · 任务视频回放</h3></div><div class="task-controls"><select v-model="task" aria-label="视频任务"><option value="">选择真实任务</option><option v-for="item in tasks" :key="item.task_id" :value="item.task_id">{{item.task_id}} · {{item.status}}</option></select><button class="primary" :disabled="busy||!task" @click="load">打开任务视频</button><button :disabled="busy" @click="discover">刷新任务</button></div></div>
   <p class="data-note"><span class="status-dot"></span>真实任务录像，非实时监控；经本平台后端播放。摄像头 GIS 绑定为示范位置，像素轨迹不转换为经纬度。{{playbackNotice}}</p>
   <p v-if="error" class="error-banner" role="alert">{{error}}</p>
   <div class="video-grid"><article v-for="camera in ['cam1','cam2']" :key="camera" class="video-card"><div class="camera-label"><b>{{camera.toUpperCase()}}</b><span>原始摄像头编号 · {{activeTask?'任务回放':'等待选择任务'}}</span></div><video v-if="activeTask" :key="activeTask+camera" :ref="playerRef" :src="`/api/videos/tasks/${encodeURIComponent(activeTask)}/${camera}`" controls autoplay muted playsinline preload="auto" @error="error='任务视频播放失败，请检查视频源或浏览器编码支持'"/><div v-else class="video-empty"><span class="reticle">◎</span><b>视频通道待命</b><small>选择真实任务后播放；不使用虚假视频备用源。</small></div></article></div>
   <div class="video-results"><div class="results-head"><div><span class="eyebrow">CROSS-CAMERA MATCHES</span><h3>关联 LIVE 跨镜结果</h3></div><strong>{{paths.length}} <small>个匿名对象</small></strong></div><div v-if="paths.length" class="path-buttons"><button v-for="path in paths" :key="path.global_id" :class="{active:selected===path.global_id}" @click="selected=path.global_id">{{path.global_id}} <small>匹配分数 {{path.score}}</small></button></div><p v-else class="results-empty">请选择并打开任务，以读取已有跨镜匹配结果；不会生成虚构对象。</p><template v-for="path in paths.filter(item=>item.global_id===selected)" :key="path.global_id"><div class="selected-route"><b>{{path.global_id}}</b><span>{{path.nodes.map(node=>node.camera_id).join(' → ')}}</span><small>{{path.start_time}} 至 {{path.end_time}}</small></div><details><summary>原始视频像素轨迹与检测框（不投影到 GIS）</summary><pre>{{JSON.stringify(path.raw_pixel_tracks,null,2)}}</pre></details></template></div>
  </section>
 </section>
</template>

<style scoped>
.video-workspace{flex:1;min-height:0;overflow:auto;color:#e2fafa;background:radial-gradient(circle at 50% -50%,rgba(45,135,151,.2),transparent 55%),#0d3040}.eyebrow{font-size:10px;letter-spacing:2px;color:#5cdbd8;font-weight:700}.video-sections{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}.video-sections button{display:grid;grid-template-columns:34px 1fr;grid-template-rows:auto auto;text-align:left;padding:10px 14px;background:#0a2d3d;border:1px solid #2e6676;color:#a7cbd1}.video-sections button>span{grid-row:1/3;align-self:center;font-size:19px;color:#4f8995}.video-sections b{font-size:14px;color:#e4f9fa}.video-sections small{font-size:10px;margin-top:2px;color:#84adb6}.video-sections button.active{border-color:#48d9d0;background:linear-gradient(110deg,#0d5260,#0c3545);box-shadow:inset 3px 0 #4bddd2}.video-sections button.active>span{color:#66eee0}.analysis-view{min-width:0}.cross-camera-section{border:1px solid #2f6f7e;background:#0b2d3d;padding:12px}.video-toolbar{display:flex;justify-content:space-between;gap:16px;align-items:end}.video-toolbar h3{margin:5px 0;font-size:17px}.task-controls{display:flex;gap:7px;flex-wrap:wrap}.task-controls select,.task-controls button{padding:8px 10px;border:1px solid #327487;background:#0a3445;color:#dff7fa;border-radius:3px}.task-controls select{min-width:230px}.task-controls button.primary{background:#087986;border-color:#31bfc3;color:#fff;font-weight:700}.task-controls button:disabled{opacity:.5}.data-note{border-left:2px solid #45d9ce;background:#0b3545;padding:8px 12px;color:#9fc9d0;font-size:11px;margin:12px 0}.status-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#51ddce;margin-right:8px}.error-banner{padding:8px 11px;background:#4b2b31;color:#ffccd0;border:1px solid #955765}.video-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.video-card{min-width:0;background:#071e2b;border:1px solid #2a687a;padding:0;overflow:hidden}.camera-label{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:#0c3445;border-bottom:1px solid #2a6376}.camera-label b{font-size:13px;color:#6ee4da}.camera-label span{font-size:10px;color:#91bbc5}video{display:block;width:100%;aspect-ratio:16/9;background:#030e16}.video-empty{aspect-ratio:16/9;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:8px;background:#071e2b;color:#b1d0d7}.video-empty .reticle{font-size:45px;color:#3c9aa8}.video-results{margin-top:10px;background:#0a2d3e;border:1px solid #2b6577;padding:10px}.results-head{display:flex;justify-content:space-between;align-items:center}.results-head h3{font-size:16px;margin:4px 0}.results-head strong{font-size:24px;color:#60e3d7}.results-head strong small{font-size:11px}.path-buttons{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0}.path-buttons button{background:#113f50;border:1px solid #397487;color:#e1f9fb;padding:7px 10px}.path-buttons button.active{border-color:#4be0d8}.path-buttons small{display:block;font-size:10px}.results-empty{font-size:11px;color:#8eafba}.selected-route{display:flex;gap:12px;border-top:1px solid #2f6574;padding-top:10px;font-size:12px}.video-results pre{max-height:180px;overflow:auto}@media(max-width:900px){.video-toolbar{align-items:start;flex-direction:column}.video-grid,.video-sections{grid-template-columns:1fr}}
</style>
