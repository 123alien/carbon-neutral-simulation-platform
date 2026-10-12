<script setup lang="ts">
import EmptyState from './EmptyState.vue'
import {onBeforeUnmount,onMounted,ref,watch,nextTick} from 'vue'
import * as echarts from 'echarts'
import type {EChartsOption} from 'echarts'
const props=withDefaults(defineProps<{option:EChartsOption;loading?:boolean;empty?:boolean;height?:string}>(),{height:'320px'})
const el=ref<HTMLDivElement>();let chart:echarts.ECharts|undefined,observer:ResizeObserver|undefined,disposed=false
const draw=async()=>{await nextTick();if(disposed||!el.value)return;chart??=echarts.init(el.value);chart.setOption({tooltip:{trigger:'axis'},legend:{top:0},...props.option},true);props.loading?chart.showLoading('default',{text:'加载中'}):chart.hideLoading()}
const resize=()=>chart?.resize();watch(()=>[props.option,props.loading],draw,{deep:true});onMounted(()=>{draw();window.addEventListener('resize',resize);observer=new ResizeObserver(resize);if(el.value)observer.observe(el.value)});onBeforeUnmount(()=>{disposed=true;observer?.disconnect();window.removeEventListener('resize',resize);chart?.dispose()})
</script>
<template><div class="chart-wrap" :style="{height}"><div ref="el" class="chart-canvas"/><EmptyState v-if="empty&&!loading" title="暂无图表数据" description="接入业务数据后将在此展示趋势"/></div></template>
