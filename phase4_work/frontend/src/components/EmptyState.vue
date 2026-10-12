<script setup lang="ts">defineProps<{title?:string;description?:string}>();</script>
<template><div class="state-box"><el-icon><Box/></el-icon><strong>{{title||'暂无数据'}}</strong><span>{{description||'当前范围内尚未接入有效数据'}}</span><slot/></div></template>
