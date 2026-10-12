<script setup lang="ts">
import {computed,ref} from 'vue'
import type {BuildingResult,ActivityPath} from '../types'
const props=defineProps<{features:any[];boundary:any;roads:any[];rows:BuildingResult[];paths:ActivityPath[];metric:string;layers:{boundary:boolean;buildings:boolean;heat:boolean;hotspots:boolean;activities:boolean}}>()
const emit=defineEmits<{select:[BuildingResult]}>()
const zoom=ref(1),pan=ref({x:0,y:0}),chosen=ref<ActivityPath>()
let drag:{x:number;y:number;px:number;py:number}|undefined
// WGS84 is projected locally in metres before the oblique display projection.
function point(c:number[],height=0){const e=(c[0]-114.42966)*111320*Math.cos(30.42023*Math.PI/180),n=(c[1]-30.42023)*111320;return [e*.9-n*.35,-e*.35-n*.85-height]}
const polygons=(f:any):number[][][][]=>f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[f.geometry.coordinates]
function outline(rings:number[][][],h=0){return rings.map(r=>r.map((c,i)=>`${i?'L':'M'}${point(c,h).join(',')}`).join(' ')+' Z').join(' ')}
const border=computed(()=>props.boundary?.features.flatMap(polygons)||[])
const box=computed(()=>{const ps=border.value.flat(2).length?border.value.flatMap((p:number[][][])=>p.flat().map(c=>point(c))):[[0,0],[100,100]];const xs=ps.map((p:number[])=>p[0]),ys=ps.map((p:number[])=>p[1]);const x=Math.min(...xs)-35,y=Math.min(...ys)-60;return [x,y,Math.max(...xs)-x+35,Math.max(...ys)-y+45]})
const viewBox=computed(()=>box.value.join(' '))
const value=(r:BuildingResult)=>props.metric==='carbon'?r.emission_t:r.energy_kwh
const max=computed(()=>Math.max(1,...props.rows.map(value)))
const threshold=computed(()=>{const v=props.rows.map(value).sort((a,b)=>a-b);return v[Math.max(0,Math.ceil(v.length*.75)-1)]??Infinity})
const palette=['#42c9dd','#3cdbab','#d7d865','#ffac57','#f06e59']
function color(r?:BuildingResult){return r&&props.layers.heat?palette[Math.min(4,Math.floor(Math.max(0,value(r))/max.value*4))]:'#b7cbca'}
const buildings=computed(()=>props.features.flatMap(f=>polygons(f).map((rings,index)=>{const row=props.rows.find(r=>r.building_id===f.properties.building_id);const height=row?42:22;const ring=rings[0];const ps=ring.slice(0,-1).map(c=>point(c));const center=[ps.reduce((a,c)=>a+c[0],0)/ps.length,ps.reduce((a,c)=>a+c[1],0)/ps.length];return {id:f.properties.building_id+'-'+index,row,rings,height,center,name:row?.name||(f.properties.verified?f.properties.name:'未核名建筑'),roof:outline(rings,height),walls:ring.slice(0,-1).map((c,i)=>[point(c),point(ring[i+1]),point(ring[i+1],height),point(c,height)].map(p=>p.join(',')).join(' ')),depth:Math.max(...ps.map(p=>p[1]))}})).sort((a,b)=>a.depth-b.depth))
const roads=computed(()=>props.roads.flatMap(f=>{const lines=f.geometry.type==='MultiLineString'?f.geometry.coordinates:[f.geometry.coordinates];return lines.map((r:number[][])=>({points:r.map(c=>point(c).join(',')).join(' '),foot:['footway','path','steps'].includes(f.properties.highway)}))}))
const tracks=computed(()=>props.paths.map((p,i)=>({path:p,color:['#a949eb','#008cff','#ef8e17','#00a47b','#e4496c'][i%5],nodes:p.nodes.filter(n=>Number.isFinite(n.longitude)&&Number.isFinite(n.latitude)),lines:(p.segments?p.segments.map(s=>s.coordinates):[p.nodes.filter(n=>Number.isFinite(n.longitude)&&Number.isFinite(n.latitude)).map(n=>[n.longitude,n.latitude])]).filter(l=>l.length>1).map(l=>l.map(c=>point(c,3).join(',')).join(' '))})))
const transform=computed(()=>`translate(${pan.value.x} ${pan.value.y}) translate(${box.value[0]+box.value[2]/2} ${box.value[1]+box.value[3]/2}) scale(${zoom.value}) translate(${-box.value[0]-box.value[2]/2} ${-box.value[1]-box.value[3]/2})`)
function down(e:PointerEvent){if((e.target as Element).closest('.relief-building,.relief-track'))return;drag={x:e.clientX,y:e.clientY,px:pan.value.x,py:pan.value.y};(e.currentTarget as SVGElement).setPointerCapture(e.pointerId)}
function move(e:PointerEvent){if(!drag)return;const r=(e.currentTarget as SVGElement).getBoundingClientRect(),s=Math.max(box.value[2]/r.width,box.value[3]/r.height);pan.value={x:drag.px+(e.clientX-drag.x)*s,y:drag.py+(e.clientY-drag.y)*s}}
const fmt=(n:number)=>n.toLocaleString('zh-CN',{maximumFractionDigits:1})
const labels=computed(()=>{
 const placed:{x:number;y:number;b:typeof buildings.value[number];width:number}[]=[]
 for(const b of buildings.value.filter(b=>b.row)){
  const width=Math.max(100,b.name.replace('湖北经济学院','').length*17+24),x=b.center[0],base=b.center[1]-b.height-22
  let y=base
  for(let attempt=0;attempt<10&&placed.some(p=>Math.abs(p.x-x)<(p.width+width)/2+8&&Math.abs(p.y-y)<35);attempt++)y-=36
  placed.push({x,y,b,width})
 }
 return placed
})
</script>
<template>
 <div class="relief-stage" data-testid="campus-relief">
  <svg :viewBox="viewBox" role="img" aria-label="湖北经济学院2.5D立体校园" @pointerdown="down" @pointermove="move" @pointerup="drag=undefined" @pointercancel="drag=undefined" @wheel.prevent="zoom=Math.max(.65,Math.min(2.8,zoom+(($event.deltaY<0)?.1:-.1)))">
   <defs><marker id="relief-route-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker><radialGradient id="relief-glow"><stop offset="0" stop-color="#ffb35d" stop-opacity=".55"/><stop offset="1" stop-color="#ffb35d" stop-opacity="0"/></radialGradient></defs>
   <g :transform="transform">
    <path v-for="(p,i) in border" :key="'land'+i" :d="outline(p)" fill="#c5d8ba" :stroke="layers.boundary?'#149f9c':'none'" stroke-width="3" :stroke-dasharray="layers.boundary?'9 5':undefined" fill-rule="evenodd"/>
    <g class="relief-roads"><g v-for="(r,i) in roads" :key="i"><polyline :points="r.points" fill="none" stroke="#e4e9dc" :stroke-width="r.foot?5:12" stroke-linejoin="round"/><polyline :points="r.points" fill="none" :stroke="r.foot?'#c5c7b9':'#637978'" :stroke-width="r.foot?2:8"/><polyline v-if="!r.foot" :points="r.points" fill="none" stroke="#e5f0e8" stroke-width=".8" stroke-dasharray="5 6"/></g></g>
    <g v-if="layers.heat"><ellipse v-for="b in buildings.filter(b=>b.row)" :key="b.id" :cx="b.center[0]" :cy="b.center[1]" rx="65" ry="35" fill="url(#relief-glow)" :opacity="b.row?Math.max(.15,value(b.row)/max):0"/></g>
    <g v-if="layers.buildings"><g v-for="b in buildings" :key="b.id" class="relief-building" :data-building-id="b.row?.building_id" :role="b.row?'button':undefined" :tabindex="b.row?0:undefined" :aria-label="b.row?b.name+'建筑详情':undefined" @click="b.row&&emit('select',b.row)" @keydown.enter="b.row&&emit('select',b.row)">
     <title>{{b.name}} · {{b.row?'已绑定业务':'仅真实轮廓，无业务指标'}}</title>
     <polygon v-for="(w,i) in b.walls" :key="i" :points="w" :fill="i%2?'#637e87':'#a6babd'" stroke="#576f76" stroke-width=".6"/>
     <g v-if="b.row" class="relief-windows"><path v-for="floor in [1,2,3]" :key="floor" :d="outline(b.rings,b.height*floor/4)" fill="none" stroke="#345560" stroke-width="3" stroke-dasharray="7 3"/></g>
     <path class="relief-roof" :d="b.roof" :fill="color(b.row)" stroke="#edf6ee" stroke-width="1.3" fill-rule="evenodd"/>
    </g></g>
    <g v-if="layers.hotspots"><g v-for="b in buildings.filter(b=>b.row&&value(b.row)>=threshold)" :key="b.id" class="relief-hotspot"><circle :cx="b.center[0]" :cy="b.center[1]-b.height-8" r="7" fill="#ed6b54" stroke="white" stroke-width="2"/></g></g>
    <g v-if="layers.activities"><g v-for="t in tracks" :key="t.path.global_id" class="relief-track" :data-global-id="t.path.global_id" @click="chosen=t.path"><polyline v-for="(line,i) in t.lines" :key="i" :points="line" fill="none" :stroke="t.color" stroke-width="4" stroke-dasharray="9 5" marker-end="url(#relief-route-arrow)"/><g v-for="(n,i) in t.nodes" :key="i"><circle :cx="point([n.longitude,n.latitude],3)[0]" :cy="point([n.longitude,n.latitude],3)[1]" :r="i===0||i===t.nodes.length-1?6:4" :fill="t.color" stroke="white" stroke-width="2"><title>{{t.path.global_id}} · {{n.camera_id}} · {{n.timestamp}}</title></circle></g></g></g>
    <g v-if="layers.buildings" class="relief-labels"><g v-for="l in labels" :key="l.b.id" @click="l.b.row&&emit('select',l.b.row)"><line :x1="l.x" :y1="l.b.center[1]-l.b.height" :x2="l.x" :y2="l.y" stroke="#326570" stroke-width="1.5"/><rect :x="l.x-l.width/2" :y="l.y-27" :width="l.width" height="32" rx="7" fill="#123e4f" stroke="#8bd6d7" stroke-width="1"/><text :x="l.x" :y="l.y-5" text-anchor="middle" fill="white" font-size="18" font-weight="600">{{l.b.name.replace('湖北经济学院','')}}</text></g></g>
   </g>
  </svg>
  <div class="relief-tools"><button aria-label="立体校园缩小" @click="zoom=Math.max(.65,zoom-.2)">−</button><button @click="zoom=1;pan={x:0,y:0}">复位</button><button aria-label="立体校园放大" @click="zoom=Math.min(2.8,zoom+.2)">＋</button></div>
  <div v-if="chosen" class="relief-path-detail"><button @click="chosen=undefined">关闭</button><b>{{chosen.global_id}} · {{chosen.activity_type}}</b><p>{{chosen.nodes.map(n=>n.camera_id).join(' → ')}}</p><p>综合匹配分数 {{fmt(chosen.score)}} · {{chosen.start_time}} 至 {{chosen.end_time}}</p><small>沿真实道路推测，非连续GPS路径；接入点待复核。不连通路段仅显示节点。</small></div>
  <span class="relief-notice">真实轮廓与道路 · 高度/立面/道路宽度示意 · 指标为示范仿真数据</span>
 </div>
</template>
<style scoped>
.relief-stage{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,#edf4ed,#c8dddf);overflow:hidden}.relief-stage svg{width:100%;height:100%;touch-action:none;cursor:grab}.relief-building[role=button],.relief-track,.relief-labels{cursor:pointer}.relief-tools{position:absolute;left:12px;bottom:38px;display:flex;gap:4px}.relief-tools button{background:#174a59;color:#e7fcff;padding:6px 10px}.relief-notice{position:absolute;left:12px;bottom:10px;font-size:10px;color:#315867;pointer-events:none}.relief-path-detail{position:absolute;left:12px;bottom:80px;max-width:340px;background:#103b4eef;padding:12px;color:#d6f5f5;font-size:11px}.relief-path-detail button{float:right}.relief-path-detail b{display:block}.relief-path-detail p{line-height:1.7}
</style>
