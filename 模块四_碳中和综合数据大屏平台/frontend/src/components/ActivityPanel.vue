<script setup lang="ts">
import {ref,computed,watch,onBeforeUnmount} from 'vue'
import type {ActivityResult,ActivityPath} from '../types'
const emit=defineEmits<{paths:[ActivityPath[]];select:[string]}>(),source=ref('DEMO'),task=ref(''),startTime=ref(''),data=ref<ActivityResult>(),error=ref(''),busy=ref(false),kinds=ref<string[]>([]),globalId=ref(''),score=ref(0),camera=ref(''),selected=ref<ActivityPath>(),selectedIds=ref<string[]>([])
let controller:AbortController|undefined
watch(selected,p=>emit('select',p?.global_id||''))
const liveStatus=ref('尚未检查连接'),timeNotice=ref(''),tasks=ref<{task_id:string;status:string}[]>([])
async function connect(){try{const h=await fetch('/api/activities/health');const status=await h.json();if(!h.ok)throw new Error(status.detail);liveStatus.value=status.message;timeNotice.value=status.time_notice||'';if(!startTime.value)startTime.value=status.video_start_time||'';if(status.status==='LIVE_READY'){const r=await fetch('/api/activities/tasks');const rows=await r.json();if(!r.ok)throw new Error(rows.detail);tasks.value=rows.filter((x:{status:string})=>x.status==='finished');if(!task.value)task.value=tasks.value[0]?.task_id||''}}catch(e){liveStatus.value=(e as Error).message}}
watch(source,s=>{if(s==='LIVE')void connect()})
const categories=computed(()=>[...new Set(data.value?.paths.map(p=>p.activity_type)||[])])
const visible=computed(()=>data.value?.paths.filter(p=>kinds.value.includes(p.activity_type)&&(!globalId.value||p.global_id.toLowerCase().includes(globalId.value.toLowerCase()))&&p.score>=score.value&&(!camera.value||p.nodes.some(n=>n.camera_id===camera.value)))||[])
const displayed=computed(()=>data.value?.paths.filter(p=>selectedIds.value.includes(p.global_id))||[])
watch(displayed,p=>emit('paths',p))
watch(source,()=>{controller?.abort();data.value=undefined;selected.value=undefined;selectedIds.value=[];error.value='';emit('paths',[])})
function toggle(p:ActivityPath){const i=selectedIds.value.indexOf(p.global_id);if(i>=0){selectedIds.value.splice(i,1);if(selected.value?.global_id===p.global_id)selected.value=undefined}else{selectedIds.value.push(p.global_id);selected.value=p}}
function clearPaths(){selectedIds.value=[];selected.value=undefined}
async function load(){controller?.abort();controller=new AbortController();const active=controller;busy.value=true;error.value='';try{const response=await fetch('/api/activities/paths',{method:'POST',headers:{'Content-Type':'application/json'},signal:active.signal,body:JSON.stringify({source:source.value,task_id:task.value||null,video_start_time:startTime.value||null})});const text=await response.text();let result:any={};if(text){try{result=JSON.parse(text)}catch{throw new Error('轨迹服务返回格式异常，请重试')}}if(!response.ok)throw new Error(result.detail||`轨迹读取失败（${response.status}）`);if(!text)throw new Error('轨迹服务暂无响应，请重试');if(active.signal.aborted)return;data.value=result;kinds.value=[...categories.value];const first=result.paths?.[0];selectedIds.value=first?[first.global_id]:[];selected.value=first}catch(e){if(!active.signal.aborted)error.value=(e as Error).message}finally{if(controller===active)busy.value=false}}
onBeforeUnmount(()=>controller?.abort())
</script>
<template>
  <section class="panel activity-panel grow">
    <h2>跨镜活动路径</h2>
    <div class="activity-row"><select v-model="source"><option value="DEMO">示范路径</option><option value="LIVE">真实接口</option></select><button :disabled="busy" @click="load">{{busy?'读取中':'加载轨迹'}}</button></div>
    <template v-if="source==='LIVE'"><p>{{liveStatus}}</p><button @click="connect">刷新任务</button><select v-model="task"><option value="">自动选择真实任务</option><option v-for="t in tasks" :key="t.task_id" :value="t.task_id">{{t.task_id}} · 已完成</option></select><input v-model="startTime" placeholder="视频开始时间（含时区）"><p v-if="timeNotice">{{timeNotice}}</p></template>
    <p v-if="error" class="notice">{{error}}；可切换示范路径。</p>
    <p class="activity-source">{{data?.data_notice||'选择数据源并加载；加载后先显示第一条轨迹，再按需逐条叠加。'}}</p>
    <div v-if="data" class="activity-stats"><span><b>{{visible.length}}</b>候选</span><span><b>{{displayed.length}}</b>已叠加</span><span><b>{{new Set(displayed.flatMap(p=>p.nodes.map(n=>n.camera_id))).size}}</b>摄像头</span></div>
    <div class="activity-kinds"><label v-for="kind in categories" :key="kind" :class="{active:kinds.includes(kind)}"><input v-model="kinds" type="checkbox" :value="kind">{{kind}}</label></div>
    <article v-if="selected" class="selected-activity"><div><b>{{selected.global_id}}</b><span>{{selected.activity_type}}</span></div><p>{{selected.nodes.map(n=>n.camera_name||n.camera_id).join(' → ')}}</p><small>{{selected.route_distance_m??0}} 米 · {{selected.route_status==='ROUTED'?'道路路径已推算':selected.route_status==='PARTIAL'?'部分路段待确认':'仅摄像头节点'}}</small><button @click="toggle(selected)">移除该轨迹</button></article>
    <div v-if="displayed.length" class="activity-row"><button @click="clearPaths">清空已叠加轨迹</button></div>
    <details v-if="data" class="object-picker" open><summary>逐条添加轨迹（{{displayed.length}}/{{visible.length}}）</summary><input v-model="globalId" placeholder="输入匿名 Global ID"><select v-model="camera"><option value="">全部摄像头</option><option v-for="c in data.cameras" :key="c.camera_id" :value="c.camera_id">{{c.camera_name||c.camera_id}}</option></select><label>最低匹配分数 <input v-model.number="score" type="number" min="0" max="1" step=".05"></label><div class="activity-list"><button v-for="p in visible" :key="p.global_id" :class="{active:selectedIds.includes(p.global_id)}" @click="toggle(p)">{{selectedIds.includes(p.global_id)?'− 移除':'+ 加入'}} {{p.global_id}} · {{p.activity_type}}</button></div></details>
    <details v-if="data?.routing_notice" class="activity-rules"><summary>道路推算与数据说明</summary><p>{{data.routing_notice}}</p><p>{{data.disclaimer}}</p></details>
    <p v-for="w in data?.warnings" :key="w">{{w}}</p>
  </section>
</template>
