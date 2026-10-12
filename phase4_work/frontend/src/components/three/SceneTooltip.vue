<script setup lang="ts">
import type {SpatialSceneObject} from '@/types'
defineProps<{item:SpatialSceneObject|null;x:number;y:number}>()
const names:Record<string,string>={PV:'分布式光伏',WIND:'风力发电',STORAGE:'储能系统',HVAC:'空调系统',LIGHTING:'照明系统',EV_CHARGER:'充电设施',ELECTRIC_METER:'电力计量设备'}
const typeName=(value:string)=>names[value.toUpperCase()]||value
</script>
<template><div v-if="item" class="three-tooltip" :style="{left:`${x+12}px`,top:`${y+12}px`}"><b>{{item.name}}</b><span>{{item.kind==='BUILDING'?'建筑':typeName(item.type)}}</span><span>{{item.coordinate.source==='LOCAL'?'园区局部坐标':'GIS 地理坐标'}}</span><span v-if="item.quality==='NO_DATA'">当前图层暂无专项指标</span></div></template>
