<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, computed, defineAsyncComponent } from "vue";
import L from "leaflet";
import "leaflet.heat";
import type { BuildingResult, ActivityPath, DeviceStatus } from "../types";
import CampusRelief from './CampusRelief.vue';
import {sharedRoads} from '../routeDisplay';
const CampusTwin = defineAsyncComponent(() => import('./CampusTwin.vue'));
const view = ref('gis'), spatialBoundary = ref<any>(), spatialRoads = ref<any[]>([]), spatialFeatures = ref<any[]>([]);
const props = defineProps<{ rows: BuildingResult[]; paths: ActivityPath[]; devices?:DeviceStatus[]; selectedGlobalId?:string }>();
const host = ref<HTMLElement>(),
  count = ref(0),
  error = ref(""),
  selected = ref<BuildingResult>(),
  metric = ref("carbon"),
  tileError = ref(false);
const layers = ref({
  boundary: true,
  buildings: true,
  heat: true,
  hotspots: true,
  activities: true,
  sensors: true,
});
let map: L.Map | undefined,
  border: L.GeoJSON | undefined,
  footprints = L.layerGroup(),
  hotspots = L.layerGroup(),
  sensors = L.layerGroup(),
  heat: L.HeatLayer | undefined;
const trajectoryGroups = new Map<string, L.LayerGroup>();
const combinedRoutes=L.layerGroup(),highlightRoute=L.layerGroup();
let features: any[] = [];
const abort = new AbortController();
const threshold = computed(() => {
  const values = props.rows.map(value).sort((a, b) => a - b);
  return values[Math.max(0, Math.ceil(values.length * 0.75) - 1)] ?? Infinity;
});
function value(r: BuildingResult) {
  return metric.value === "carbon" ? r.emission_t : r.energy_kwh;
}
function sync(layer: L.Layer, enabled: boolean) {
  if (!map) return;
  enabled ? layer.addTo(map) : layer.remove();
}
function render() {
  if (!map || view.value !== 'gis') return;
  footprints.clearLayers();
  hotspots.clearLayers();
  heat?.remove();
  const points: L.HeatLatLngTuple[] = [];
  const max = Math.max(1, ...props.rows.map(value));
  for (const f of features) {
    const row = props.rows.find(
      (r) => r.building_id === f.properties.building_id,
    );
    const name =
      row?.name || (f.properties.verified ? f.properties.name : "未核名建筑");
    const shape = L.geoJSON(f, {
      style: {
        color: row ? "#00a99d" : "#47747d",
        weight: row ? 2 : 1,
        fillColor: row ? "#45d8bb" : "#dce9e7",
        fillOpacity: row ? 0.25 : 0.12,
      },
    });
    const text = document.createElement("span");
    text.textContent = String(name);
    shape.bindTooltip(text);
    if (row) {
      shape.on("click", () => (selected.value = row));
      const c = shape.getBounds().getCenter();
      points.push([c.lat, c.lng, Math.max(0.18, value(row) / max)]);
      if (value(row) >= threshold.value) {
        const icon = L.divIcon({
          className: "hotspot-host",
          html: `<span class="hotspot ${metric.value}">${metric.value === "carbon" ? "高碳" : "高耗"}</span>`,
          iconSize: [42, 22],
          iconAnchor: [21, 11],
        });
        L.marker(c, { icon })
          .on("click", () => (selected.value = row))
          .addTo(hotspots);
      }
    }
    shape.addTo(footprints);
  }
  sync(footprints, layers.value.buildings);
  sync(hotspots, layers.value.hotspots);
  if (border) sync(border, layers.value.boundary);
  if (points.length && layers.value.heat)
    heat = L.heatLayer(points, {
      radius: 38,
      blur: 30,
      maxZoom: 19,
      minOpacity: 0.28,
      gradient: {
        0.2: "#39c6ff",
        0.45: "#38df9b",
        0.7: "#ffd24d",
        1: "#ef3f35",
      },
    }).addTo(map);
}
function renderSensors(){
  if(!map||view.value!=='gis')return;
  sensors.clearLayers();
  for(const device of props.devices||[]){
    if(!device.building_id)continue;
    const feature=features.find(f=>f.properties.building_id===device.building_id);
    if(!feature)continue;
    const center=L.geoJSON(feature).getBounds().getCenter(),wrap=document.createElement('div');
    const title=document.createElement('b');title.textContent=`设备 ${device.device_name||device.device_id}`;wrap.append(title);
    const place=document.createElement('p');place.textContent=`${device.floor_id||device.building_id} · ${device.online?'在线':'离线'}`;wrap.append(place);
    for(const factor of device.factors||[]){const row=document.createElement('div');row.textContent=`${factor.metric_name||'指标'}：${factor.value??'—'} ${factor.unit||''}`;wrap.append(row)}
    const power=device.factors?.find(f=>f.metric_code==='power_kw'||f.metric_name==='实时功率');
    const meter=Boolean(power),label=meter?`${Number(power?.value||0).toLocaleString('zh-CN',{maximumFractionDigits:1})} kW`:(device.online?'●':'!');
    L.marker(center,{icon:L.divIcon({className:`sensor-marker ${meter?'meter-hotspot':''}`,html:`<span class="${device.online?'online':'offline'}">${label}</span>`,iconSize:meter?[72,30]:[24,24],iconAnchor:meter?[36,15]:[12,12]})}).bindTooltip(wrap).addTo(sensors)
  }
  sync(sensors,layers.value.sensors)
}
const colors = ["#ffcc49", "#e87eff", "#49caff", "#5fe0a1", "#ff866d"];
function drawPaths() {
  if (!map) return;
  // Shared road edges are drawn once; source trajectories remain unchanged.
  for(const g of trajectoryGroups.values())g.remove();
  trajectoryGroups.clear();
  combinedRoutes.clearLayers();highlightRoute.clearLayers();
  if(!layers.value.activities){combinedRoutes.remove();highlightRoute.remove();return;}
  combinedRoutes.addTo(map);highlightRoute.addTo(map);
  const parts=sharedRoads(props.paths);
  for(const part of parts){
    const coordinates=part.coordinates.map(c=>[c[1],c[0]] as L.LatLngTuple);
    const text=document.createElement('span');
    text.textContent=`道路推测 · 共${part.ids.size}条轨迹经过 · ${[...part.ids].join('、')}`;
    L.polyline(coordinates,{className:'cross-camera-route',color:'#40d4e6',weight:3,opacity:.75,dashArray:'8 6'}).bindTooltip(text).addTo(combinedRoutes);
  }
  // One count label on the longest shared edge of each membership group.
  const labels=new Map<string,typeof parts[number]>();
  for(const part of parts){if(part.ids.size<2)continue;const key=[...part.ids].sort().join(',');
    const length=(p:typeof part)=>Math.hypot(p.coordinates[1][0]-p.coordinates[0][0],p.coordinates[1][1]-p.coordinates[0][1]);
    if(!labels.has(key)||length(part)>length(labels.get(key)!))labels.set(key,part);
  }
  for(const part of labels.values()){
    const [a,b]=part.coordinates;
    L.marker([(a[1]+b[1])/2,(a[0]+b[0])/2],{icon:L.divIcon({className:'shared-route-count',html:`<span style="background:#083b4e;color:#ddffff;border:1px solid #49cddd;border-radius:9px;padding:1px 5px;white-space:nowrap;font-size:10px">${part.ids.size}条</span>`,iconSize:[32,16],iconAnchor:[16,8]})}).bindTooltip(`共${part.ids.size}条轨迹经过`).addTo(combinedRoutes);
  }
  const cameraNodes=new Map<string,ActivityPath['nodes'][number]>();
  for(const p of props.paths)for(const n of p.nodes)if(Number.isFinite(n.latitude)&&Number.isFinite(n.longitude))cameraNodes.set(n.camera_id,n);
  for(const n of cameraNodes.values())L.circleMarker([n.latitude,n.longitude],{radius:5,color:'#40d4e6',fillOpacity:1}).bindTooltip(n.camera_name||n.camera_id).addTo(combinedRoutes);
  const chosen=props.paths.find(p=>p.global_id===props.selectedGlobalId)||props.paths[0];
  if(chosen)for(const segment of chosen.segments||[]){
    const line=segment.coordinates.map(c=>[c[1],c[0]] as L.LatLngTuple);if(line.length<2)continue;
    L.polyline(line,{className:'active-route-shadow',color:'#06384e',weight:9,opacity:.8}).addTo(highlightRoute);
    L.polyline(line,{className:'active-cross-camera-route',color:'#00e7ff',weight:5,opacity:1,dashArray:'12 7'}).bindTooltip(`${chosen.global_id} · 单人道路推测路径（非GPS）`).addTo(highlightRoute);
    const a=line[line.length-2],b=line[line.length-1];
    const angle=Math.atan2((b[1]-a[1])*Math.cos(b[0]*Math.PI/180),-(b[0]-a[0]))*180/Math.PI;
    L.circleMarker(line[0],{className:'route-endpoint',radius:8,color:'#fff',weight:2,fillColor:'#00d9ba',fillOpacity:1}).bindTooltip(`${chosen.global_id} · 起点`,{permanent:true,direction:'left'}).addTo(highlightRoute);
    L.circleMarker(b,{className:'route-endpoint',radius:8,color:'#fff',weight:2,fillColor:'#ff725c',fillOpacity:1}).bindTooltip(`${chosen.global_id} · 终点`,{permanent:true,direction:'right'}).addTo(highlightRoute);
    L.marker(b,{interactive:false,icon:L.divIcon({className:'route-direction',html:`<span style="display:block;color:#00e7ff;text-shadow:0 0 5px #002d3a;transform:rotate(${angle}deg);font-size:20px">▲</span>`,iconSize:[20,20],iconAnchor:[10,10]})}).addTo(highlightRoute);
  }
}
watch(() => [props.rows, metric.value, layers.value], render, { deep: true });
watch(() => [props.devices, layers.value.sensors], renderSensors, {deep:true});
watch(() => [props.paths, props.selectedGlobalId, layers.value.activities], drawPaths, { deep: true });
watch(view, () => {
  heat?.remove();
  requestAnimationFrame(() => {
    if (view.value === 'gis') { map?.invalidateSize(); render(); renderSensors(); drawPaths(); }
  });
}, {flush:'sync'});
onMounted(async () => {
  try {
    const [b, f, roads] = await Promise.all(
      ["boundary", "buildings", "roads"].map(async (x) => {
        const r = await fetch(`/api/spatial/${x}`, { signal: abort.signal });
        if (!r.ok) throw new Error("校园空间文件加载失败");
        return r.json();
      }),
    );
    if (!host.value || abort.signal.aborted) return;
    map = L.map(host.value, {
      zoomControl: false,
      zoomAnimation: false,
      fadeAnimation: false,
      minZoom: 14,
      maxZoom: 19,
    });
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors · ODbL",
    })
      .on("tileerror", () => (tileError.value = true))
      .addTo(map);
    border = L.geoJSON(b, {
      style: {
        color: "#008a91",
        weight: 3,
        dashArray: "8 5",
        fillOpacity: 0.04,
      },
    }).addTo(map);
    const bounds = border.getBounds();
    map.fitBounds(bounds, { padding: [8, 8] });
    map.setZoom(Math.min(19, map.getZoom() + 1));
    map.setMaxBounds(bounds.pad(0.35));
    features = f.features;
    spatialBoundary.value = b;
    spatialFeatures.value = f.features;
    spatialRoads.value = roads.features;
    count.value = features.length;
    render();
    renderSensors();
    drawPaths();
  } catch (e) {
    if (!abort.signal.aborted) error.value = (e as Error).message;
  }
});
onBeforeUnmount(() => {
  abort.abort();
  map?.remove();
  map = undefined;
});
const fmt = (n: number) =>
  n.toLocaleString("zh-CN", { maximumFractionDigits: 1 });
</script>
<template>
  <section class="map-panel" :class="{'relief-view':view!=='gis'}">
    <div class="map-head">
      <span>校园 GIS 能碳态势</span
      ><div class="spatial-switch"><button :class="{active:view==='gis'}" @click="view='gis'">GIS地图</button><button :class="{active:view==='relief'}" @click="view='relief'">2.5D立体校园</button><button :class="{active:view==='twin'}" @click="view='twin'">3D校园沙盘</button></div><select v-model="metric" aria-label="空间热力指标">
        <option value="carbon">碳排热力</option>
        <option value="energy">能耗热力</option>
      </select>
    </div>
    <div class="map-stage">
      <div v-show="view==='gis'" ref="host" class="map" />
      <CampusRelief v-if="view==='relief'&&spatialBoundary" :features="spatialFeatures" :boundary="spatialBoundary" :roads="spatialRoads" :rows="rows" :paths="paths" :metric="metric" :layers="layers" @select="selected=$event" />
      <CampusTwin v-if="view==='twin'&&spatialBoundary" :features="spatialFeatures" :boundary="spatialBoundary" :roads="spatialRoads" :rows="rows" :paths="paths" :metric="metric" :layers="layers" @select="selected=$event" />
      <div class="gis-title">
        <small>校园 GIS 能碳态势</small><b>湖北经济学院</b
        ><span>WGS84 · EPSG:4326</span
        ><em>建筑轮廓 {{ count }} · 业务绑定 {{ rows.length }}</em>
      </div>
      <div class="layer-control">
        <b>图层控制</b
        ><label
          v-for="(name, key) in {
            boundary: '校园边界',
            buildings: '建筑轮廓',
            heat: '能碳热力',
            hotspots: '高值热点',
            activities: '跨镜路径',
            sensors: '实测设备',
          }"
          :key="key"
          ><input v-model="layers[key]" type="checkbox" />{{ name }}</label
        ><small>能碳指标为模块一示范仿真结果</small>
      </div>
      <div class="gis-legend">
        <b>{{ metric === "carbon" ? "碳排放" : "用电量" }}热力</b><i /><span
          >低</span
        ><span>高</span>
      </div>
      <div v-if="selected" class="detail">
        <button @click="selected = undefined">关闭</button>
        <h3>{{ selected.name }}</h3>
        <p>建筑编号：{{ selected.building_id }}</p>
        <p>本年累计用电：{{ fmt(selected.energy_kwh) }} kWh</p>
        <p>本年累计用水：{{ fmt(selected.water_m3) }} m³</p>
        <p>本年累计碳排：{{ fmt(selected.emission_t) }} tCO₂e</p>
        <p>
          直接／间接排放：{{ fmt(selected.scope1_t) }}／{{
            fmt(selected.scope2_t)
          }}
          tCO₂e
        </p>
        <p>当前功率：{{ fmt(selected.power_kw) }} kW</p>
        <p>数据性质：示范仿真数据，非学校实测</p>
      </div>
    </div>
    <footer>
      {{
        error ||
        "125栋真实轮廓保留；未绑定建筑不分配指标。沿道路推测跨镜路径，非GPS；不连通仅显示节点。"
      }}
    </footer>
  </section>
</template>
