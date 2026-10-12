<script setup lang="ts">
import {onMounted,onBeforeUnmount,watch,ref} from 'vue'
import * as echarts from 'echarts/core'
import {LineChart,BarChart,GaugeChart,SankeyChart,RadarChart} from 'echarts/charts'
import {GridComponent,TooltipComponent,LegendComponent,MarkPointComponent,MarkLineComponent,RadarComponent} from 'echarts/components'
import {CanvasRenderer} from 'echarts/renderers'
echarts.use([LineChart,BarChart,GaugeChart,SankeyChart,RadarChart,GridComponent,TooltipComponent,LegendComponent,MarkPointComponent,MarkLineComponent,RadarComponent,CanvasRenderer])
const props=defineProps<{option:any}>(),host=ref<HTMLElement>();let chart:echarts.ECharts|undefined,observer:ResizeObserver|undefined
onMounted(()=>{if(!host.value)return;chart=echarts.init(host.value);chart.setOption(props.option);observer=new ResizeObserver(()=>chart?.resize());observer.observe(host.value)})
watch(()=>props.option,v=>chart?.setOption(v,true),{deep:true})
onBeforeUnmount(()=>{observer?.disconnect();chart?.dispose();chart=undefined})
</script>
<template><div ref="host" class="chart"/></template>
<style scoped>.chart{flex:1 1 0;min-height:0;width:100%;position:relative}</style>
