<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import SceneToolbar from "./SceneToolbar.vue";
import SceneLegend from "./SceneLegend.vue";
import SceneTooltip from "./SceneTooltip.vue";
import type {
  Building,
  Device,
  HourlySimulationPoint,
  Site,
  SpatialLayerMode,
  SpatialSceneObject,
} from "@/types";
import { validateSpatial } from "@/utils/spatial";
import { normalizeAsset, disposeObject, campusEnvironment } from "@/utils/campusGeometry";
import { businessBuilding } from "@/utils/businessBuildings";
import {campusFootprintGround,detailedCampusBuildings,footprintCenter,type CampusFeature,type CampusRoad,type CampusLandscape} from '@/utils/hbueFootprintBuildings';
import {campusArchitecture,coreCampusBuildings} from '@/utils/campusArchitecture';
const campusFeatures=ref<CampusFeature[]>([]),campusBoundary=ref<CampusFeature>();
const campusRoads=ref<CampusRoad[]>([]);
const campusLandscape=ref<CampusLandscape[]>([]);
const showWholeCampus=ref(false);
const isHbue=computed(()=>props.site.code==='HBUE'||props.site.metadata_json?.campus_id==='HBUE');
function footprintFor(source:Building){const id=String(source.metadata_json?.building_id||source.code);return campusFeatures.value.find(f=>f.properties.building_id===id)}
const props = withDefaults(
  defineProps<{
    site: Site;
    buildings: Building[];
    devices?: Device[];
    compact?: boolean;
    hourly?: HourlySimulationPoint[];
    timeIndex?: number;
  }>(),
  { devices: () => [], compact: false, hourly: () => [], timeIndex: 0 },
);
const emit = defineEmits<{
  building: [Building];
  device: [Device];
  level: [string];
}>();
const host = ref<HTMLElement>(),
  mode = ref<SpatialLayerMode>("DEVICE"),
  level = ref<"SITE" | "BUILDING" | "DEVICE">("SITE"),
  selectedBuilding = ref<Building | null>(null),
  selectedDevice = ref<Device | null>(null),
  hovered = ref<SpatialSceneObject | null>(null),
  tip = ref({ x: 0, y: 0 });
let renderer: THREE.WebGLRenderer | undefined,
  scene: THREE.Scene | undefined,
  camera: THREE.PerspectiveCamera | undefined,
  controls: OrbitControls | undefined,
  frame = 0,
  resize: ResizeObserver | undefined;
const ray = new THREE.Raycaster(),
  mouse = new THREE.Vector2(),
  gltfLoader = new GLTFLoader(),
  pickables: THREE.Object3D[] = [],
  sceneObjects: THREE.Object3D[] = [];
let rebuildVersion=0;
const pendingAssets=ref(0);
function assetFinished(version:number){if(version===rebuildVersion)pendingAssets.value=Math.max(0,pendingAssets.value-1);}
let environment: THREE.Group | undefined;
const buildingRoots = new Map<number, THREE.Object3D>();
const labels=ref<{id:number;name:string;x:number;y:number;item:SpatialSceneObject}[]>([]);
const buildingValidation = computed(() =>{
  const result=validateSpatial(props.buildings, props.site, "BUILDING");
  if(isHbue.value)result.objects=result.objects.filter(item=>coreCampusBuildings.has(String((item.source as Building).metadata_json?.building_id||(item.source as Building).code)));
  if(isHbue.value)for(const item of result.objects){const f=footprintFor(item.source as Building);if(f){const c=footprintCenter(f);item.coordinate={x:c.x,y:0,z:c.y,source:'GEOGRAPHIC'}}}
  return result;
});
const deviceValidation = computed(() => {
  const validation=validateSpatial(props.devices,props.site,"DEVICE");
  const parents=new Map(buildingValidation.value.objects.map(item=>[item.id,item]));
  if(isHbue.value)validation.objects=validation.objects.filter(item=>parents.has(Number((item.source as Device).metadata_json?.building_id)));
  for(const item of validation.objects) {
    const d=item.source as Device, parent=parents.get(Number(d.metadata_json?.building_id));
    if(item.coordinate.source!=='LOCAL') continue;
    if(!parent) {if(item.type.includes('METER'))item.coordinate={...item.coordinate,y:0};continue;}
    const p=parent.coordinate, type=item.type.toUpperCase();
    // Existing demo device positions are building-local, not global elevation.
    let x=p.x+item.coordinate.x,z=p.z+item.coordinate.z,y=p.y;
    if(type.includes('PV')||type.includes('HVAC')) {x=p.x;z=p.z;y=p.y+Number((parent.source as Building).floor_count||3)*2.8;}
    else if(type.includes('STORAGE')) {x=p.x+17;z=p.z+3;}
    else if(type.includes('WIND')) {x=p.x+24;z=p.z+9;}
    else if(type.includes('CHARG')||type.includes('EV')) {x=p.x;z=p.z+16;}
    else if(type.includes('METER')) {x=p.x+12;z=p.z+7;}
    item.coordinate={x,y,z,source:'LOCAL'};
  }
  return validation;
});
const invalidCount=computed(()=>buildingValidation.value.invalidCount+deviceValidation.value.invalidCount);
const visible=computed(()=>[
  ...buildingValidation.value.objects,
  ...deviceValidation.value.objects.filter(item=>{
    if(level.value==='SITE') return true;
    if(level.value==='DEVICE') return item.id===selectedDevice.value?.id;
    return Number((item.source as Device).metadata_json?.building_id)===selectedBuilding.value?.id;
  }),
]);
const hasSpatial = computed(
  () =>
    buildingValidation.value.objects.length > 0 ||
    deviceValidation.value.objects.length > 0,
);
function color(item: SpatialSceneObject) {
  if (item.quality === "NO_DATA" && mode.value !== "DEVICE") return 0x64748b;
  if (item.kind === "BUILDING")
    return mode.value === "CARBON"
      ? 0x22c55e
      : mode.value === "ENERGY"
        ? 0x38bdf8
        : 0x14b8a6;
  const t = item.type.toUpperCase();
  return t.includes("PV")
    ? 0xfbbf24
    : t.includes("WIND")
      ? 0x60a5fa
      : t.includes("STORAGE")
        ? 0xa78bfa
        : t.includes("CHARG")
          ? 0xfb7185
          : 0x2dd4bf;
}
const mat=(hex:number,metalness=.12,roughness=.62)=>new THREE.MeshPhysicalMaterial({color:hex,metalness,roughness,clearcoat:.18,clearcoatRoughness:.42,emissive:hex,emissiveIntensity:.018})
function mesh(geometry:THREE.BufferGeometry,material:THREE.Material,item:SpatialSceneObject){const value=new THREE.Mesh(geometry,material);value.castShadow=true;value.receiveShadow=true;value.userData.item=item;pickables.push(value);return value}
function facadeMaterial(wall:string,glass:string,floors:number){
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=512;const ctx=canvas.getContext('2d')!;
  ctx.fillStyle=wall;ctx.fillRect(0,0,512,512);
  const rows=Math.max(3,Math.min(12,floors)),rowHeight=512/rows;
  for(let row=0;row<rows;row++){
    ctx.fillStyle=row%2?'rgba(255,255,255,.07)':'rgba(0,0,0,.035)';ctx.fillRect(0,row*rowHeight,512,rowHeight);
    ctx.fillStyle='rgba(34,46,48,.24)';ctx.fillRect(0,row*rowHeight,512,5);
    for(let bay=0;bay<8;bay++){
      const x=bay*64+11,y=row*rowHeight+13,w=42,h=Math.max(18,rowHeight-27);
      const gradient=ctx.createLinearGradient(x,y,x+w,y+h);gradient.addColorStop(0,glass);gradient.addColorStop(.45,'#9fc6cf');gradient.addColorStop(.48,'#476b76');gradient.addColorStop(1,'#244b59');
      ctx.fillStyle='#d7dfdc';ctx.fillRect(x-3,y-3,w+6,h+6);ctx.fillStyle=gradient;ctx.fillRect(x,y,w,h);
      ctx.fillStyle='rgba(255,255,255,.38)';ctx.fillRect(x+4,y+3,2,h-7);
    }
  }
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=renderer?.capabilities.getMaxAnisotropy()||4;
  return new THREE.MeshPhysicalMaterial({map:texture,color:0xffffff,roughness:.57,metalness:.06,clearcoat:.12,clearcoatRoughness:.62});
}
function buildingModel(item:SpatialSceneObject,height:number){
  const group=new THREE.Group(),source=item.source as Building;
  const facade=facadeMaterial('#d9ddd8','#416473',Number(source.floor_count||3));
  const block=mesh(new THREE.BoxGeometry(22,height,17),facade,item);block.position.y=height/2;group.add(block);
  const roof=mesh(new THREE.BoxGeometry(22.4,.22,17.4),mat(0x687477),item);roof.position.y=height+.11;group.add(roof);
  const entrance=mesh(new THREE.BoxGeometry(4,2.8,.25),mat(0x365566,.2,.3),item);entrance.position.set(0,1.4,8.6);group.add(entrance);
  const canopy=mesh(new THREE.BoxGeometry(5,.18,2),mat(0xc7cece),item);canopy.position.set(0,2.9,9);group.add(canopy);
  return group;
}
function deviceModel(item:SpatialSceneObject){
  const group=new THREE.Group(),type=item.type.toUpperCase(),c=color(item)
  if(type.includes('PV')){for(let r=0;r<2;r++)for(let i=0;i<4;i++){const panel=mesh(new THREE.BoxGeometry(2.1,.12,1.25),mat(0x125b87,.55,.18),item);panel.position.set((i-1.5)*2.25,.8+r*.12,(r-.5)*1.4);panel.rotation.x=-.28;group.add(panel)}const inverter=mesh(new THREE.BoxGeometry(1.1,1.5,.7),mat(0xe6edf0,.25,.35),item);inverter.position.set(5,.75,0);group.add(inverter)}
  else if(type.includes('WIND')){const tower=mesh(new THREE.CylinderGeometry(.18,.55,9,16),mat(0xdce7ea,.35,.28),item);tower.position.y=4.5;group.add(tower);const nacelle=mesh(new THREE.BoxGeometry(1.5,.55,.65),mat(0xe7eff1,.3,.28),item);nacelle.position.set(.45,9.05,0);group.add(nacelle);const hub=mesh(new THREE.SphereGeometry(.35,16,12),mat(c,.3,.3),item);hub.position.set(-.35,9.05,.36);group.add(hub);for(let a=0;a<3;a++){const blade=mesh(new THREE.BoxGeometry(.16,3.5,.08),mat(0xd5e4e8,.25,.3),item);blade.position.set(-.35,9.05,.38);blade.geometry.translate(0,1.65,0);blade.rotation.z=a*Math.PI*2/3;group.add(blade)}}
  else if(type.includes('STORAGE')){const box=mesh(new THREE.BoxGeometry(5,2.7,2.4),mat(0xe8eceb,.45,.3),item);box.position.y=1.35;group.add(box);for(let i=-1;i<=1;i++){const vent=mesh(new THREE.BoxGeometry(.75,1.35,.08),mat(0x445b60,.55,.25),item);vent.position.set(i*1.25,1.45,1.24);group.add(vent)}const lamp=mesh(new THREE.SphereGeometry(.12,8,8),mat(c,.1,.15),item);lamp.position.set(2,2.25,1.3);group.add(lamp)}
  else if(type.includes('CHARG')||type.includes('EV')){for(let i=0;i<3;i++){const post=mesh(new THREE.BoxGeometry(.55,2,.5),mat(0xeff4f3,.32,.3),item);post.position.set((i-1)*1.4,1,0);group.add(post);const screen=mesh(new THREE.PlaneGeometry(.3,.38),mat(c,.2,.2),item);screen.position.set((i-1)*1.4,1.35,.255);group.add(screen)}}
  else if(type.includes('HVAC')){for(let i=0;i<2;i++){const unit=mesh(new THREE.BoxGeometry(2.3,1.4,1.8),mat(0xb9c7c9,.4,.38),item);unit.position.set((i-.5)*2.6,.7,0);group.add(unit);const fan=mesh(new THREE.CylinderGeometry(.55,.55,.08,20),mat(0x3e5960,.5,.25),item);fan.rotation.x=Math.PI/2;fan.position.set((i-.5)*2.6,.8,.94);group.add(fan)}}
  else if(type.includes('LIGHT')){for(let i=0;i<3;i++){const pole=mesh(new THREE.CylinderGeometry(.06,.09,3.2,10),mat(0x70858a,.5,.28),item);pole.position.set((i-1)*1.7,1.6,0);group.add(pole);const lamp=mesh(new THREE.BoxGeometry(.75,.14,.3),mat(0xffe6a0,.2,.2),item);lamp.position.set((i-1)*1.7+.28,3.15,0);group.add(lamp)}}
  else{const meter=type.includes('METER'),w=meter ? .72 : 2.2,h=meter ? 1.15 : 2.4,d=meter ? .35 : 1.5;const cabinet=mesh(new THREE.BoxGeometry(w,h,d),mat(c,.35,.38),item);cabinet.position.y=h/2;group.add(cabinet);const badge=mesh(new THREE.PlaneGeometry(w*.45,h*.24),mat(0xb8fff1,.15,.2),item);badge.position.set(0,h*.62,d/2+.006);group.add(badge)}
  return group
}
const buildingAssets=['building-a.glb','building-c.glb','building-f.glb','building-j.glb'];
function buildingAsset(item:SpatialSceneObject){
  const source=item.source as Building;
  if(Number(source.floor_count||0)>=18)return 'building-skyscraper-a.glb';
  const type=source.building_type.toUpperCase();
  if(type.includes('OFFICE'))return 'building-j.glb';
  if(type.includes('LAB'))return 'building-f.glb';
  if(type.includes('SERVICE'))return 'building-a.glb';
  const key=Math.abs(Number(source.id)||0)%buildingAssets.length;
  return buildingAssets[key];
}
function register(root:THREE.Object3D,item:SpatialSceneObject) {
  root.userData.item=item;
  root.traverse(node=>{
    const mesh=node as THREE.Mesh;
    if(!mesh.isMesh)return;
    mesh.castShadow=true;mesh.receiveShadow=true;mesh.userData.item=item;
    // Preserve single-material meshes: an array requires geometry groups.
    for(const m of (Array.isArray(mesh.material)?mesh.material:[mesh.material])) {
      const material=m as THREE.MeshStandardMaterial;
      material.roughness=.68;material.metalness=.04;
      if(material.map)material.map.anisotropy=Math.min(8,renderer?.capabilities.getMaxAnisotropy()||1);
    }
    if(!pickables.includes(mesh))pickables.push(mesh);
  });
}
function removeRoot(root:THREE.Object3D) {
  scene?.remove(root);
  const index=sceneObjects.indexOf(root);if(index>=0)sceneObjects.splice(index,1);
  root.traverse(node=>{const i=pickables.indexOf(node);if(i>=0)pickables.splice(i,1)});
  disposeObject(root);
}
function placeDevice(root:THREE.Object3D,item:SpatialSceneObject) {
  const c=item.coordinate;
  root.position.set(c.x,c.y,c.z);
  const parent=buildingRoots.get(Number((item.source as Device).metadata_json?.building_id));
  if(parent&&(item.type.includes('PV')||item.type.includes('HVAC'))) {
    parent.updateWorldMatrix(true,true);
    const bounds=new THREE.Box3().setFromObject(parent);
    const roofRay=new THREE.Raycaster(new THREE.Vector3(c.x,bounds.max.y+5,c.z),new THREE.Vector3(0,-1,0));
    const hit=roofRay.intersectObject(parent,true)[0];
    root.position.y=(hit?.point.y??bounds.max.y)+.035;
  }
  root.updateMatrixWorld(true);
}
function loadBuildingAsset(item:SpatialSceneObject,height:number,placeholder:THREE.Object3D,version:number) {
  gltfLoader.load('/models/kenney-commercial/'+buildingAsset(item),gltf=>{
    if(!scene||version!==rebuildVersion){disposeObject(gltf.scene);return;}
    let model=normalizeAsset(gltf.scene,new THREE.Vector3(22,height,17));
    const source=item.source as Building,type=source.building_type.toUpperCase();
    if(type.includes('OFFICE')||type.includes('LAB')||type.includes('SERVICE')){
      const roofRay=new THREE.Raycaster(new THREE.Vector3(0,height+5,0),new THREE.Vector3(0,-1,0));
      const roofHeight=roofRay.intersectObject(model,true)[0]?.point.y??height-.35;
      const replacement=businessBuilding(type,Number(source.floor_count||3),height,roofHeight);
      disposeObject(model);model=replacement;
    }
    model.position.set(item.coordinate.x,item.coordinate.y,item.coordinate.z);
    removeRoot(placeholder);register(model,item);scene.add(model);sceneObjects.push(model);buildingRoots.set(item.id,model);
    for(const root of sceneObjects){const object=root.userData.item as SpatialSceneObject|undefined;if(object?.kind==='DEVICE')placeDevice(root,object);}
    assetFinished(version);applyFocus();
  },undefined,()=>{assetFinished(version);});
}
function loadDeviceAsset(item:SpatialSceneObject,placeholder:THREE.Object3D,version:number) {
  const type=item.type.toUpperCase();
  const file=type.includes('PV')?'solar-panel-landscape-group.glb':type.includes('WIND')?'windmill.glb':null;
  if(!file)return;
  gltfLoader.load('/models/kenney-industrial/'+file,gltf=>{
    if(!scene||version!==rebuildVersion){disposeObject(gltf.scene);return;}
    const model=normalizeAsset(gltf.scene,type.includes('WIND')?new THREE.Vector3(1,14,1):new THREE.Vector3(10,1.4,5),type.includes('WIND'));
    removeRoot(placeholder);register(model,item);placeDevice(model,item);scene.add(model);sceneObjects.push(model);assetFinished(version);applyFocus();
  },undefined,()=>{assetFinished(version);});
}
function clearObjects() {
  for(const root of [...sceneObjects]) removeRoot(root);
  buildingRoots.clear();labels.value=[];
}
let environmentKey='';
let renderNeeded=true;
function invalidate(shadows=false){renderNeeded=true;if(shadows&&renderer)renderer.shadowMap.needsUpdate=true}
function rebuild() {
  if(!scene)return;
  const version=++rebuildVersion;clearObjects();
  const all=[...buildingValidation.value.objects,...deviceValidation.value.objects];
  pendingAssets.value=isHbue.value?0:all.filter(item=>item.kind==='BUILDING'||item.type.includes('PV')||item.type.includes('WIND')).length;
  const nextEnvironmentKey=`${props.site.id}:${campusFeatures.value.length}:${campusRoads.value.length}`;
  if(!isHbue.value||!environment||nextEnvironmentKey!==environmentKey){
  if(environment){scene.remove(environment);disposeObject(environment);}
  environment=isHbue.value&&campusBoundary.value?campusFootprintGround(campusFeatures.value,campusBoundary.value,campusRoads.value,new Set(buildingValidation.value.objects.map(i=>String((i.source as Building).metadata_json?.building_id||(i.source as Building).code))),campusLandscape.value):campusEnvironment(buildingValidation.value.objects.map(item=>item.coordinate),deviceValidation.value.objects.map(item=>({...item.coordinate,type:item.type})));scene.add(environment);
  if(host.value){host.value.dataset.backgroundBuildings=String(environment.userData.background_building_count||0);host.value.dataset.landscapeCount=String(environment.userData.landscape_count||0)}
  environmentKey=nextEnvironmentKey;
  }
  for(const item of all) {
    const height=item.kind==='BUILDING'?Math.max(5,Number((item.source as Building).floor_count||3)*2.8):2.5;
    const footprint=item.kind==='BUILDING'&&isHbue.value?footprintFor(item.source as Building):undefined;
    const detailed=footprint&&detailedCampusBuildings.has(footprint.properties.building_id||'');
    const model=item.kind==='BUILDING'?(footprint?campusArchitecture(footprint,height,Number((item.source as Building).floor_count||3)):buildingModel(item,height)):deviceModel(item);
    model.position.set(item.coordinate.x,item.coordinate.y,item.coordinate.z);
    register(model,item);scene.add(model);sceneObjects.push(model);
    if(item.kind==='BUILDING'){buildingRoots.set(item.id,model);if(!footprint)loadBuildingAsset(item,height,model,version);else if(!detailed)assetFinished(version);}
    else {placeDevice(model,item);if(!isHbue.value)loadDeviceAsset(item,model,version);}
  }
  applyFocus();
}
function applyFocus() {
  invalidate(true);
  for(const root of sceneObjects){
    const item=root.userData.item as SpatialSceneObject|undefined;
    if(!item)continue;
    root.visible=item.kind==='BUILDING'||(level.value==='SITE'?!item.type.includes('METER'):(level.value==='DEVICE'?item.id===selectedDevice.value?.id:Number((item.source as Device).metadata_json?.building_id)===selectedBuilding.value?.id));
  }
}
function reset() {
  if (!camera || !controls) return;
  const focusObjects=level.value==='BUILDING'&&selectedBuilding.value?visible.value.filter(x=>x.kind==='BUILDING'&&x.id===selectedBuilding.value?.id||x.kind==='DEVICE'&&Number((x.source as Device).metadata_json?.building_id)===selectedBuilding.value?.id):visible.value;
  const cluster=isHbue.value&&!showWholeCampus.value&&level.value==='SITE'?focusObjects.filter(x=>x.kind==='BUILDING'&&detailedCampusBuildings.has(String((x.source as Building).metadata_json?.building_id||(x.source as Building).code))):focusObjects;
  const objects=cluster.length?cluster:focusObjects,center=new THREE.Vector3();
  if(objects.length){for(const item of objects){center.x+=item.coordinate.x;center.z+=item.coordinate.z}center.x/=objects.length;center.z/=objects.length}
  center.y=4;
  const footprint=selectedBuilding.value&&isHbue.value?footprintFor(selectedBuilding.value):undefined;
  const extent=footprint?Math.max(...footprint.geometry.coordinates[0].map(p=>Math.hypot((p[0]-114.42966)*111320*Math.cos(30.42023*Math.PI/180)-center.x,-(p[1]-30.42023)*111320-center.z))):0;
  const radius=Math.max(28,extent,...objects.map((item)=>Math.hypot(item.coordinate.x-center.x,item.coordinate.z-center.z)))+18;
  camera.position.set(center.x+radius*1.12,Math.max(65,radius*1.2),center.z+radius*1.42);
  controls.target.copy(center);
  controls.update();
  invalidate();
}
function focusCampusBuilding(building:Building){selectedBuilding.value=building;selectedDevice.value=null;level.value='BUILDING';emit('building',building);applyFocus();reset()}
function campusView(whole:boolean){showWholeCampus.value=whole;selectedBuilding.value=null;selectedDevice.value=null;level.value='SITE';applyFocus();reset()}
function init() {
  if (!host.value) return;
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xdce8ec);
  scene.fog=new THREE.Fog(0xdce8ec,220,450);
  camera = new THREE.PerspectiveCamera(45, 1, .8, isHbue.value?5000:1800);
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.25));
  renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
  renderer.shadowMap.autoUpdate=false;renderer.shadowMap.needsUpdate=true;
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.12;
  host.value.appendChild(renderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.addEventListener('change',()=>invalidate());
  controls.enableDamping = true;
  controls.maxPolarAngle=Math.PI*.46;controls.minDistance=15;controls.maxDistance=isHbue.value?2500:340;
  if(isHbue.value)scene.fog=new THREE.Fog(0xdce8ec,1800,4000);
  scene.add(new THREE.HemisphereLight(0xe9f6fb, 0x54686b, 1.35));
  const sun = new THREE.DirectionalLight(0xfff4df, 2.35);
  sun.position.set(30, 80, 20);
  sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-100;sun.shadow.camera.right=100;sun.shadow.camera.top=100;sun.shadow.camera.bottom=-100;sun.shadow.bias=-.0002;sun.shadow.camera.far=220;sun.shadow.normalBias=.04;sun.shadow.camera.updateProjectionMatrix();
  scene.add(sun);
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(900,900),new THREE.MeshStandardMaterial({color:0xc1ceca,roughness:1}));
  ground.rotation.x=-Math.PI/2;ground.position.y=-.5;ground.receiveShadow=true;if(!isHbue.value)scene.add(ground);else{ground.geometry.dispose();(ground.material as THREE.Material).dispose()}
  reset();
  resize = new ResizeObserver(() => fit());
  resize.observe(host.value);
  renderer.domElement.addEventListener("pointermove", pointerMove);
  renderer.domElement.addEventListener("click", click);
  rebuild();
  animate();
}
function fit() {
  if (!host.value || !camera || !renderer) return;
  const w = host.value.clientWidth,
    h = host.value.clientHeight;
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
  invalidate();
}
function hit(e: MouseEvent | PointerEvent) {
  if (!renderer || !camera) return null;
  const r = renderer.domElement.getBoundingClientRect();
  mouse.set(
    ((e.clientX - r.left) / r.width) * 2 - 1,
    (-(e.clientY - r.top) / r.height) * 2 + 1,
  );
  ray.setFromCamera(mouse, camera);
  return ray.intersectObjects(pickables.filter(mesh=>{
    let node:THREE.Object3D|null=mesh;
    while(node){if(!node.visible)return false;node=node.parent;}return true;
  }))[0]?.object.userData.item as
    SpatialSceneObject | undefined;
}
function pointerMove(e: PointerEvent) {
  hovered.value = hit(e) || null;
  const r = renderer!.domElement.getBoundingClientRect();
  tip.value = { x: e.clientX - r.left, y: e.clientY - r.top };
}
function click(e: MouseEvent) {
  const item = hit(e);
  if (!item) return;
  if (item.kind === "BUILDING") {
    selectedBuilding.value = item.source as Building;
    level.value = "BUILDING";
    emit("building", selectedBuilding.value);
  } else {
    selectedDevice.value = item.source as Device;
    level.value = "DEVICE";
    emit("device", selectedDevice.value);
  }
  emit("level", level.value);
  applyFocus();
  reset();
}
function back() {
  if (level.value === "DEVICE") {
    level.value = "BUILDING";
    selectedDevice.value = null;
  } else {
    level.value = "SITE";
    selectedBuilding.value = null;
  }
  emit("level", level.value);
  applyFocus();
  reset();
}
let renderedFrames=0;
function animate() {
  frame = requestAnimationFrame(animate);
  controls?.update();
  if (scene && camera && renderNeeded) {
    renderNeeded=false;
    renderer?.render(scene,camera);
    if(host.value&&renderer){host.value.dataset.renderCount=String(++renderedFrames);host.value.dataset.drawCalls=String(renderer.info.render.calls)}
    const w=host.value?.clientWidth||1,h=host.value?.clientHeight||1;
    const candidates=buildingValidation.value.objects;
    const projected=candidates.flatMap(item=>{
      const root=buildingRoots.get(item.id);if(!root)return [];
      let anchor=root.userData.labelAnchor as THREE.Vector3|undefined;
      if(!anchor){const bounds=new THREE.Box3().setFromObject(root);anchor=bounds.getCenter(new THREE.Vector3());anchor.y=bounds.max.y+2;root.userData.labelAnchor=anchor}
      const p=anchor.clone().project(camera!);
      return p.z<1&&Math.abs(p.x)<.95&&Math.abs(p.y)<.9?[{id:item.id,name:item.name,x:(p.x+1)*w/2,y:(1-p.y)*h/2,item}]:[];
    });
    const clean:typeof projected=[];for(const original of projected){const p={...original};while(clean.some(q=>Math.abs(q.x-p.x)<140&&Math.abs(q.y-p.y)<30)&&p.y>50)p.y-=32;clean.push(p)}
    if(clean.length!==labels.value.length||clean.some((p,i)=>p.id!==labels.value[i]?.id||Math.abs(p.x-labels.value[i].x)>.25||Math.abs(p.y-labels.value[i].y)>.25))labels.value=clean;
  }
}
function dispose() {
  ++rebuildVersion;
  cancelAnimationFrame(frame);
  resize?.disconnect();
  if (renderer) {
    renderer.domElement.removeEventListener("pointermove", pointerMove);
    renderer.domElement.removeEventListener("click", click);
  }
  clearObjects();
  controls?.dispose();
  scene?.traverse((o) => {
    const m = o as THREE.Mesh;
    m.geometry?.dispose();
  });
  if(scene)disposeObject(scene);
  renderer?.dispose();
  renderer?.domElement.remove();
  scene = renderer = camera = controls = undefined;
}
// Rebuild only when geometry changes, not on every live energy snapshot.
const geometrySignature=computed(()=>JSON.stringify([
 buildingValidation.value.objects.map(i=>{const b=i.source as Building;return [i.id,i.coordinate,i.type,b.floor_count,b.position_json,b.metadata_json?.model_asset,b.metadata_json?.building_id]}),
 deviceValidation.value.objects.map(i=>[i.id,i.coordinate,i.type,(i.source as Device).metadata_json?.model_asset]),
 campusFeatures.value,campusBoundary.value,campusRoads.value,campusLandscape.value,
]));
watch(geometrySignature,()=>nextTick(rebuild));
watch([buildingValidation,deviceValidation],()=>{
 const current=new Map([...buildingValidation.value.objects,...deviceValidation.value.objects].map(i=>[`${i.kind}:${i.id}`,i]));
 for(const object of pickables){const item=object.userData.item as SpatialSceneObject|undefined;if(item){const fresh=current.get(`${item.kind}:${item.id}`);if(fresh){item.source=fresh.source;item.name=fresh.name;}}}
});
watch([level,selectedBuilding,selectedDevice],()=>nextTick(applyFocus));
watch(
  () => props.site.id,
  () => {
    level.value = "SITE";
    selectedBuilding.value = null;
    selectedDevice.value = null;
    nextTick(() => {
      rebuild();
      reset();
    });
  },
);
onMounted(async()=>{
 if(isHbue.value){try{
  const [buildings,boundary,roads,landscape]=await Promise.all(['hbue_buildings','hbue_campus_boundary','hbue_roads','hbue_landscape'].map(async name=>{const r=await fetch(`/data/hbue/${name}.geojson`);if(!r.ok)throw new Error('校园空间资料加载失败');return r.json()}));
  campusFeatures.value=buildings.features;campusBoundary.value=boundary.features[0];campusRoads.value=roads.features;campusLandscape.value=landscape.features;
 }catch(e){if(host.value)host.value.dataset.landscapeError=String(e)}}
 init();
});
onBeforeUnmount(dispose);
</script>
<template>
  <section class="three-shell" :class="{ compact }" :data-models-ready="pendingAssets===0">
    <span v-if="isHbue&&campusFeatures.length" class="campus-model-notice">真实校园轮廓、道路与环境面 · 建筑高度和立面示意 · 背景建筑无业务指标 · © OpenStreetMap贡献者</span>
    <div v-if="isHbue&&campusFeatures.length" class="campus-focus"><button @click="campusView(false)">重点建筑区</button><button @click="campusView(true)">校园总览</button></div>
    <SceneToolbar
      :mode="mode"
      :level="level"
      :time-enabled="Boolean(hourly.length)"
      @mode="mode = $event"
      @back="back"
      @reset="reset"
    />
    <div ref="host" class="three-canvas">
      <div v-if="!hasSpatial" class="three-empty">
        当前园区暂无可用空间数据
      </div>
      <button v-for="label in labels" :key="label.id" class="campus-label" :style="{left:label.x+'px',top:label.y+'px'}" @click="focusCampusBuilding(label.item.source as Building)">{{label.name}}</button>
      <span v-if="pendingAssets" class="asset-loading">正在加载园区模型…</span>
      <SceneTooltip :item="hovered" :x="tip.x" :y="tip.y" />
    </div>
    <SceneLegend :mode="mode" /><span v-if="invalidCount" class="three-invalid"
      >已忽略 {{ invalidCount }} 条无效空间数据</span
    ><span class="three-gis"><b>园区空间示意</b><small v-if="site.longitude!=null&&site.latitude!=null">{{site.longitude.toFixed(4)}}°E · {{site.latitude.toFixed(4)}}°N</small><small v-else>园区局部坐标系</small></span><span v-if="hourly.length" class="three-time">{{
      hourly[Math.min(timeIndex, hourly.length - 1)]?.timestamp
    }}</span>
  </section>
</template>
<style scoped>
.campus-model-notice{position:absolute;left:18px;bottom:64px;z-index:4;background:#103d4ddd;color:#e8ffff;padding:6px 10px;font-size:11px}
.campus-focus{position:absolute;left:18px;top:70px;z-index:4;display:flex;gap:6px}.campus-focus button{padding:7px 10px;border:1px solid #7baab3;background:#e9f3f2;color:#164552;cursor:pointer;font-size:12px}
.asset-loading{position:absolute;bottom:100px;left:50%;transform:translateX(-50%);padding:8px 16px;border-radius:4px;background:#102e40e8;color:white;z-index:4;font-size:12px}
.campus-label{position:absolute;z-index:3;transform:translate(-50%,-100%);padding:5px 10px;border:1px solid #87c9d799;border-radius:14px;background:#133b4bdd;color:#f0fbff;font:500 11px/1.4 "Microsoft YaHei",sans-serif;box-shadow:0 2px 8px #12303d20;cursor:pointer;white-space:nowrap}.campus-label span{display:none}.campus-label:hover{background:#174f60;}
</style>
