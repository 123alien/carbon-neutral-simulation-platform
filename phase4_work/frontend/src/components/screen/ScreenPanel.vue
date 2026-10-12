<script setup lang="ts">defineProps<{title:string;link?:string;empty?:boolean;emptyText?:string}>();</script>
<template><article class="screen-panel"><header><h2>{{title}}</h2><router-link v-if="link" :to="link">查看详情 ›</router-link></header><div v-if="empty" class="screen-empty">{{emptyText||'暂无数据'}}</div><slot v-else/></article></template>
