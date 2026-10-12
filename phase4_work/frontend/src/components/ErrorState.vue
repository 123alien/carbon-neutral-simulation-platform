<script setup lang="ts">defineProps<{message?:string}>();defineEmits<{retry:[]}>();</script>
<template><div class="state-box error"><el-icon><WarningFilled/></el-icon><strong>数据加载失败</strong><span>{{message||'请检查后端服务连接后重试'}}</span><el-button @click="$emit('retry')">重新加载</el-button></div></template>
