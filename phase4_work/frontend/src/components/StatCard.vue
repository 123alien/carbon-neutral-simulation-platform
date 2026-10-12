<script setup lang="ts">
import {computed} from 'vue'
const props=defineProps<{label:string;value:number|string|null;unit?:string;hint?:string;tone?:'green'|'blue'|'amber'|'slate';digits?:number}>()
const displayValue=computed(()=>{const digits=props.digits??(typeof props.value==='number'&&Number.isInteger(props.value)?0:2);return typeof props.value==='number'?props.value.toLocaleString('zh-CN',{minimumFractionDigits:digits,maximumFractionDigits:digits}):props.value})
</script>
<template><article class="stat-card" :class="`tone-${tone||'green'}`"><div class="stat-top"><span>{{label}}</span><slot name="icon"/></div><div v-if="value!==null" class="stat-value">{{displayValue}}<small v-if="unit">{{unit}}</small></div><div v-else class="stat-empty">暂无数据</div><p>{{hint||'来自当前业务数据'}}</p></article></template>
