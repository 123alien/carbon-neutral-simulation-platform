<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount,watch} from 'vue'
import * as T from 'three'
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js'
import {mergeGeometries} from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import type {BuildingResult,ActivityPath} from '../types'
import RainEffect from './RainEffect.vue'
const props=defineProps<{features:any[];boundary:any;roads:any[];rows:BuildingResult[];paths:ActivityPath[];metric:string;layers:{boundary:boolean;buildings:boolean;heat:boolean;hotspots:boolean;activities:boolean}}>()
const emit=defineEmits<{select:[BuildingResult]}>()
const host=ref<HTMLElement>(),error=ref(''),ready=ref(false),frames=ref(0),labels=ref<{id:string;name:string;x:number;y:number}[]>([]),chosen=ref<ActivityPath>()
let scene:T.Scene,camera:T.PerspectiveCamera,renderer:T.WebGLRenderer,controls:OrbitControls,observer:ResizeObserver,frame=0,dead=false
const buildings=new T.Group(),environment=new T.Group(),border=new T.Group(),overlay=new T.Group(),activities=new T.Group()
const picks:T.Object3D[]=[],anchors:{id:string;name:string;position:T.Vector3}[]=[]
const abort=new AbortController(),materials:T.Material[]=[],geometries:T.BufferGeometry[]=[]
type WeatherMode='sunny'|'cloudy'|'rain'
const weather=ref<WeatherMode>('sunny')
const weatherSource=ref('live'),currentWeather=ref<any>(),weatherBusy=ref(false)
let weatherTimer:ReturnType<typeof setInterval>|undefined
async function refreshWeather(){if(weatherBusy.value||dead)return;weatherBusy.value=true;try{const r=await fetch('/api/weather/current',{signal:abort.signal});if(!r.ok)throw new Error();currentWeather.value=await r.json();if(weatherSource.value==='live')applyCurrentWeather()}catch{if(!dead)currentWeather.value={status:'UNAVAILABLE',data_notice:'当前天气读取失败；不使用示意天气冒充实时数据'}}finally{weatherBusy.value=false;if(weatherSource.value==='live')applyCurrentWeather()}}
function applyCurrentWeather(){if(currentWeather.value?.status==='AVAILABLE')weather.value=currentWeather.value.mode;applyWeather()}
function precipitation(){return currentWeather.value?.metrics?.find((m:any)=>m.code==='precipitation')?.value??null}
watch(weatherSource,s=>{if(s==='live'){applyCurrentWeather();void refreshWeather()}else applyWeather()})
onMounted(()=>{void refreshWeather();weatherTimer=setInterval(()=>{if(!document.hidden)void refreshWeather()},300000)})
onBeforeUnmount(()=>{if(weatherTimer)clearInterval(weatherTimer)})
const weatherModes={sunny:{name:'晴天',icon:'☀',sky:'#c5d9dd',sun:2.5,ambient:1.2,exposure:.95,near:1700,far:4000},cloudy:{name:'阴天',icon:'☁',sky:'#aabdc5',sun:.65,ambient:1.65,exposure:.9,near:1300,far:3200},rain:{name:'雨天',icon:'☂',sky:'#859da9',sun:.35,ambient:1.3,exposure:.82,near:950,far:2600}}
function applyWeather(){if(!scene||!renderer)return;const valid=weatherSource.value!=='live'||currentWeather.value?.status==='AVAILABLE',night=weatherSource.value==='live'&&currentWeather.value?.status==='AVAILABLE'&&!currentWeather.value.is_day,w=valid?weatherModes[weather.value]:weatherModes.cloudy,sky=night?'#253a50':w.sky;scene.background=new T.Color(sky);scene.fog=new T.Fog(sky,w.near,w.far);scene.traverse(o=>{if(o instanceof T.DirectionalLight){o.intensity=night?.15:w.sun;o.castShadow=valid&&!night&&weather.value==='sunny'}if(o instanceof T.HemisphereLight)o.intensity=night?.65:w.ambient});renderer.toneMappingExposure=night?.7:w.exposure;renderer.shadowMap.needsUpdate=true;invalidate()}
watch(weather,applyWeather)
watch(ready,()=>{if(weatherSource.value==='live')applyCurrentWeather();else applyWeather()})
const origin=[114.42966,30.42023],factor=111320*Math.cos(origin[1]*Math.PI/180)
function xy(c:number[]){return new T.Vector2((c[0]-origin[0])*factor,(c[1]-origin[1])*111320)}
function v3(c:number[],h=0){const p=xy(c);return new T.Vector3(p.x,h,-p.y)}
const polygons=(f:any):number[][][][]=>f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[f.geometry.coordinates]
function shape(rings:number[][][]){const s=new T.Shape(rings[0].map(xy));for(const ring of rings.slice(1))s.holes.push(new T.Path(ring.map(xy)));return s}
function material(color:string,extra:Partial<T.MeshStandardMaterialParameters>={}){const m=new T.MeshStandardMaterial({color,roughness:.82,...extra});materials.push(m);return m}
function geometry(g:T.BufferGeometry){geometries.push(g);return g}
function extrude(rings:number[][][],h:number,mat:T.Material|T.Material[],y=0){const g=geometry(new T.ExtrudeGeometry(shape(rings),{depth:h,bevelEnabled:false,steps:1}));g.rotateX(-Math.PI/2);const m=new T.Mesh(g,mat);m.position.y=y;m.castShadow=true;m.receiveShadow=true;return m}
function plane(rings:number[][][],mat:T.Material,y:number){const g=geometry(new T.ShapeGeometry(shape(rings)));g.rotateX(-Math.PI/2);const m=new T.Mesh(g,mat);m.position.y=y;m.receiveShadow=true;return m}
function inside(p:T.Vector2,ring:number[][]){let yes=false;const r=ring.map(xy);for(let i=0,j=r.length-1;i<r.length;j=i++){const a=r[i],b=r[j];if((a.y>p.y)!==(b.y>p.y)&&p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x)yes=!yes}return yes}
function ribbon(coords:number[][],width:number,y:number){const out:number[]=[];for(let i=1;i<coords.length;i++){const a=v3(coords[i-1],y),b=v3(coords[i],y),d=b.clone().sub(a);if(d.length()<.01)continue;const n=new T.Vector3(-d.z,0,d.x).normalize().multiplyScalar(width/2),p=[a.clone().add(n),a.clone().sub(n),b.clone().add(n),b.clone().sub(n)];for(const j of [0,1,2,2,1,3])out.push(p[j].x,p[j].y,p[j].z)}const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(out,3));g.computeVertexNormals();return g}
function merged(gs:T.BufferGeometry[],mat:T.Material,group:T.Group){if(!gs.length)return;const g=mergeGeometries(gs);gs.forEach(g=>g.dispose());if(g){const m=new T.Mesh(geometry(g),mat);m.receiveShadow=true;group.add(m)}}
const center=new T.Vector3(),radius=ref(650)
function home(close=true){if(!controls)return;const r=radius.value*(close?.78:1.2);controls.target.copy(center);camera.position.copy(center).add(new T.Vector3(-r*.85,r*.72,r*.9));controls.update();invalidate()}
function invalidate(){if(dead||frame)return;frame=requestAnimationFrame(()=>{frame=0;if(!renderer||!host.value||!host.value.clientWidth)return;renderer.render(scene,camera);frames.value++;const w=host.value.clientWidth,h=host.value.clientHeight;const taken:{x:number;y:number}[]=[];labels.value=props.layers.buildings?anchors.flatMap(a=>{const p=a.position.clone().project(camera);const x=(p.x+1)*w/2,y=(1-p.y)*h/2;if(p.z>1||p.z< -1||x<30||x>w-30||y<65||y>h-60||taken.some(t=>Math.abs(t.x-x)<85&&Math.abs(t.y-y)<24))return [];taken.push({x,y});return [{id:a.id,name:a.name.replace('湖北经济学院',''),x,y}]}):[]})}
function clear(group:T.Group){for(const o of [...group.children]){group.remove(o);o.traverse(x=>{const m=x as T.Mesh;m.geometry?.dispose();const ms=Array.isArray(m.material)?m.material:[m.material];ms.forEach(a=>a?.dispose())})}}
function update(){if(!scene)return;buildings.visible=props.layers.buildings;border.visible=props.layers.boundary;clear(overlay);clear(activities)
 const value=(r:BuildingResult)=>props.metric==='carbon'?r.emission_t:r.energy_kwh,max=Math.max(1,...props.rows.map(value)),vs=props.rows.map(value).sort((a,b)=>a-b),threshold=vs[Math.max(0,Math.ceil(vs.length*.75)-1)]??Infinity
 for(const a of anchors){const row=props.rows.find(r=>r.building_id===a.id);if(!row)continue;const hue=.55*(1-value(row)/max)
  if(props.layers.heat){const m=new T.Mesh(new T.RingGeometry(13,20,40),new T.MeshBasicMaterial({color:new T.Color().setHSL(hue,.9,.52),transparent:true,opacity:.45,side:T.DoubleSide,depthWrite:false}));m.rotation.x=-Math.PI/2;m.position.set(a.position.x,1.1,a.position.z);overlay.add(m)}
  if(props.layers.hotspots&&value(row)>=threshold){const m=new T.Mesh(new T.SphereGeometry(2.5,10,8),new T.MeshBasicMaterial({color:'#ff8b57'}));m.position.copy(a.position).add(new T.Vector3(0,4,0));overlay.add(m)}
 }
 if(props.layers.activities)props.paths.forEach((p,i)=>{const color=['#ffbd59','#bc7aff','#40dded','#62e0a2','#ff8079'][i%5],nodes=p.nodes.filter(n=>Number.isFinite(n.longitude)&&Number.isFinite(n.latitude)),lines=p.segments?p.segments.map(s=>s.coordinates):[nodes.map(n=>[n.longitude,n.latitude])];for(const line of lines){if(line.length<2)continue;const m=new T.Line(new T.BufferGeometry().setFromPoints(line.map(c=>v3(c,4))),new T.LineBasicMaterial({color,transparent:true,opacity:.85,depthTest:false}));m.renderOrder=8;m.userData.path=p;activities.add(m);const a=v3(line[line.length-2],4),b=v3(line[line.length-1],4),direction=b.clone().sub(a);if(direction.length()>.1){const arrow=new T.Mesh(new T.ConeGeometry(2,8,6),new T.MeshBasicMaterial({color,depthTest:false}));arrow.position.copy(b);arrow.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),direction.normalize());arrow.renderOrder=9;activities.add(arrow)}}for(const n of nodes){const m=new T.Mesh(new T.SphereGeometry(3,10,8),new T.MeshBasicMaterial({color,depthTest:false}));m.position.copy(v3([n.longitude,n.latitude],4));m.userData.path=p;m.renderOrder=9;activities.add(m)}})
 invalidate()
}
async function build(){const grass=material('#9da98a'),roof=material('#687b83'),wall=material('#e5e3d7'),backgroundWall=material('#c3c9bd'),brick=material('#b4947a'),glass=material('#274650',{roughness:.32,metalness:.2}),trim=material('#d9ddd8')
 for(const f of props.boundary.features)for(const rings of polygons(f))environment.add(plane(rings,grass,0))
 const windows:T.Matrix4[]=[],frames:T.Matrix4[]=[],units:T.Matrix4[]=[],dummy=new T.Object3D(),core=new T.Box3()
 for(const f of props.features)for(const rings of polygons(f)){
  const id=f.properties.building_id,row=props.rows.find(r=>r.building_id===id),name=row?.name||'',publicHall=/体育|活动中心|食堂|三清园/.test(name),dorm=/宿舍|公寓|苑/.test(name),floors=row?(publicHall?3:dorm?6:5):4,h=floors*3.6
  const body=extrude(rings,h,[roof,row?(dorm?brick:wall):backgroundWall]);body.userData.building_id=id;buildings.add(body);picks.push(body)
  if(!row)continue;const box=new T.Box3().setFromObject(body),c=box.getCenter(new T.Vector3());core.union(box);anchors.push({id,name,position:new T.Vector3(c.x,h+4,c.z)})
  const cap=extrude(rings,.7,trim,h);buildings.add(cap)
  const ring=rings[0]
  for(let i=1;i<ring.length;i++){const a=v3(ring[i-1]),b=v3(ring[i]),d=b.clone().sub(a),len=d.length();if(len<4)continue;const angle=Math.atan2(d.x,d.z),count=Math.floor(len/3.6),width=publicHall?2.5:1.65
   for(let floor=0;floor<floors;floor++)for(let k=0;k<count;k++){const c=a.clone().lerp(b,(k+.5)/count);dummy.position.set(c.x,floor*3.6+2.1,c.z);dummy.rotation.set(0,angle,0);dummy.scale.set(.18,publicHall?2.1:1.6,width);dummy.updateMatrix();windows.push(dummy.matrix.clone());dummy.scale.set(.24,.16,width+.4);dummy.position.y=floor*3.6+1.23;dummy.updateMatrix();frames.push(dummy.matrix.clone())}
  }
  // Roof units are decorative only, placed only where their centres are inside the true polygon.
  for(const dx of [-6,6]){const p=new T.Vector2(c.x+dx,-c.z);if(!inside(p,ring))continue;dummy.position.set(c.x+dx,h+1.4,c.z);dummy.rotation.set(0,0,0);dummy.scale.set(3,1.8,4);dummy.updateMatrix();units.push(dummy.matrix.clone())}
 }
 function instances(ms:T.Matrix4[],mat:T.Material){if(!ms.length)return;const m=new T.InstancedMesh(geometry(new T.BoxGeometry(1,1,1)),mat,ms.length);ms.forEach((a,i)=>m.setMatrixAt(i,a));m.castShadow=true;m.receiveShadow=true;buildings.add(m)}instances(windows,glass);instances(frames,trim);instances(units,roof)
 core.getCenter(center);radius.value=Math.max(420,core.getSize(new T.Vector3()).length()*.48)
 const road:T.BufferGeometry[]=[],curb:T.BufferGeometry[]=[],paths:T.BufferGeometry[]=[]
 for(const f of props.roads){const lines=f.geometry.type==='MultiLineString'?f.geometry.coordinates:[f.geometry.coordinates];const foot=['footway','path','steps'].includes(f.properties.highway);for(const l of lines){curb.push(ribbon(l,foot?3.5:10,.12));(foot?paths:road).push(ribbon(l,foot?2.5:7,.18))}}
 merged(curb,material('#d4d2bd',{side:T.DoubleSide}),environment);merged(road,material('#566265',{side:T.DoubleSide}),environment);merged(paths,material('#b9b49d',{side:T.DoubleSide}),environment)
 for(const f of props.boundary.features)for(const rings of polygons(f)){const m=new T.Line(new T.BufferGeometry().setFromPoints(rings[0].map(c=>v3(c,.4))),new T.LineBasicMaterial({color:'#489b94',transparent:true,opacity:.5}));border.add(m)}
 try{const r=await fetch('/api/spatial/landscape',{signal:abort.signal});if(r.ok){const data=await r.json();const water=material('#518994',{roughness:.3,metalness:.25}),green=material('#718764');const trees:T.Vector3[]=[];for(const f of data.features)for(const rings of polygons(f)){const wet=f.properties.landscape_type==='water';environment.add(plane(rings,wet?water:green,.25));if(!wet){const ps=rings[0].map(xy),xs=ps.map(p=>p.x),ys=ps.map(p=>p.y);for(let x=Math.min(...xs)+7;x<Math.max(...xs);x+=18)for(let y=Math.min(...ys)+7;y<Math.max(...ys);y+=18){if(trees.length>=650)break;if(inside(new T.Vector2(x,y),rings[0])&&!props.features.some(b=>polygons(b).some(r=>inside(new T.Vector2(x,y),r[0]))))trees.push(new T.Vector3(x,0,-y))}}}
 const foliage=new T.InstancedMesh(geometry(new T.SphereGeometry(1,8,6)),material('#3f6249'),trees.length),trunks=new T.InstancedMesh(geometry(new T.CylinderGeometry(.5,.65,4,5)),material('#766451'),trees.length);trees.forEach((p,i)=>{dummy.position.copy(p).add(new T.Vector3(0,6,0));dummy.scale.set(3.2+Math.sin(i*2.7)*.8,4.8+Math.cos(i*1.9),3.3+Math.cos(i*2.3)*.7);dummy.rotation.set(0,i*.6,0);dummy.updateMatrix();foliage.setMatrixAt(i,dummy.matrix);foliage.setColorAt(i,new T.Color().setHSL(.29+Math.sin(i*1.7)*.035,.26,.23+Math.cos(i*2.1)*.045));dummy.position.copy(p).add(new T.Vector3(0,2,0));dummy.scale.set(1,1,1);dummy.updateMatrix();trunks.setMatrixAt(i,dummy.matrix)});foliage.castShadow=true;environment.add(foliage,trunks)}}catch{if(!dead)error.value='景观数据暂不可用，建筑与道路仍可查看'}
 update();home();ready.value=true
}
function select(id:string){const row=props.rows.find(r=>r.building_id===id);if(row)emit('select',row)}
let down={x:0,y:0}
function pick(e:PointerEvent){if(Math.hypot(e.clientX-down.x,e.clientY-down.y)>5)return;const r=renderer.domElement.getBoundingClientRect(),ray=new T.Raycaster();ray.params.Line.threshold=5;ray.setFromCamera(new T.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),camera);const hit=ray.intersectObjects([...picks,...activities.children],false).find(h=>h.object.visible&&h.object.parent?.visible);if(hit?.object.userData.path)chosen.value=hit.object.userData.path;else if(hit)select(hit.object.userData.building_id)}
watch(()=>[props.rows,props.paths,props.metric,props.layers],update,{deep:true})
onMounted(async()=>{try{if(!host.value)return;scene=new T.Scene();scene.background=new T.Color('#c5d9dd');scene.fog=new T.Fog('#c5d9dd',1700,4000);camera=new T.PerspectiveCamera(42,1,1,6000);renderer=new T.WebGLRenderer({antialias:true,alpha:false});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=true;renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=.95;host.value.appendChild(renderer.domElement);scene.add(environment,buildings,border,overlay,activities,new T.HemisphereLight('#e6f4ff','#69734a',1.2));const sun=new T.DirectionalLight('#fff0da',2.5);sun.position.set(-500,800,400);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-1300,right:1300,top:1300,bottom:-1300,near:1,far:2500});sun.shadow.bias=-.0004;scene.add(sun);controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=false;controls.minDistance=70;controls.maxDistance=2500;controls.maxPolarAngle=Math.PI*.46;controls.addEventListener('change',invalidate);renderer.domElement.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY}});renderer.domElement.addEventListener('pointerup',pick);renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();error.value='三维渲染连接中断，请切回GIS后重试'});observer=new ResizeObserver(()=>{if(!host.value?.clientWidth)return;const w=host.value.clientWidth,h=host.value.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();invalidate()});observer.observe(host.value);await build();renderer.shadowMap.needsUpdate=true;invalidate()}catch{error.value='当前浏览器无法加载三维场景，请使用GIS或2.5D视图'}})
onBeforeUnmount(()=>{dead=true;abort.abort();cancelAnimationFrame(frame);observer?.disconnect();controls?.dispose();const gs=new Set<T.BufferGeometry>(),ms=new Set<T.Material>();scene?.traverse(o=>{const m=o as T.Mesh;if(m.geometry)gs.add(m.geometry);if(m.material)(Array.isArray(m.material)?m.material:[m.material]).forEach(a=>ms.add(a))});geometries.forEach(g=>gs.add(g));materials.forEach(m=>ms.add(m));gs.forEach(g=>g.dispose());ms.forEach(m=>m.dispose());renderer?.dispose();renderer?.forceContextLoss()})
</script>
<template>
  <div class="twin-stage" data-testid="campus-twin" :data-weather="weatherSource==='live'&&currentWeather?.status!=='AVAILABLE'?'unknown':weather" :data-ready="ready" :data-frames="frames" :data-paths="layers.activities?paths.length:0">
    <div ref="host" class="twin-canvas"/>
    <RainEffect v-if="weather==='rain'&&currentWeather?.status==='AVAILABLE'" :precipitation="precipitation()"/>
    <button v-for="l in labels" :key="l.id" class="twin-label" :style="{left:l.x+'px',top:l.y+'px'}" @click="select(l.id)">{{l.name}}</button>
    <div class="twin-tools"><button @click="home()">核心区近景</button><button @click="home(false)">校园全景</button><small>左键旋转 · 右键平移 · 滚轮缩放</small></div>
    <p v-if="error" class="twin-error">{{error}}</p>
    <div v-if="chosen" class="twin-path"><button @click="chosen=undefined">关闭</button><b>{{chosen.global_id}} · {{chosen.activity_type}}</b><p>{{chosen.nodes.map(n=>n.camera_id).join(' → ')}}</p><p>{{chosen.start_time}} 至 {{chosen.end_time}}</p><p>匹配分数 {{chosen.score}} · 沿道路推测，非GPS路径；已推算 {{chosen.route_distance_m??0}} 米</p></div>
    <span class="twin-notice">真实轮廓/道路/景观底图 · 外观、树木与高度示意 · 业务为示范仿真数据 · © OpenStreetMap / ODbL</span>
  </div>
</template>
<style scoped>.twin-stage,.twin-canvas{position:absolute;inset:0;overflow:hidden}.twin-canvas :deep(canvas){display:block;width:100%;height:100%}.twin-label{position:absolute;transform:translate(-50%,-100%);padding:4px 8px;font-size:11px;color:#e9fcff;background:#103e50df;border:1px solid #69c7c5;border-radius:12px;white-space:nowrap;box-shadow:0 3px 7px #183b4555}.twin-tools{position:absolute;bottom:40px;left:12px;display:flex;gap:5px;align-items:center}.twin-tools button{font-size:11px;background:#16485ae8;padding:6px 8px}.twin-tools small{font-size:10px;color:#244b56}.twin-notice{position:absolute;bottom:10px;left:12px;right:145px;font-size:9px;color:#294d59;pointer-events:none}.twin-error,.twin-path{position:absolute;left:12px;bottom:82px;max-width:330px;background:#103a4cf0;padding:12px;color:#e3fbff;font-size:11px}.twin-path button{float:right}</style>
