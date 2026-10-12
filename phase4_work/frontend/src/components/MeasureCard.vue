<script setup lang="ts">
defineProps<{title:string;code:string;enabled:boolean;summary:string}>()
defineEmits<{(event:'toggle',value:boolean):void}>()
</script>
<template><article class="measure-card" :class="{enabled}"><header><div><span>{{code}}</span><h3>{{title}}</h3></div><el-switch :model-value="enabled" @change="$emit('toggle',Boolean($event))"/></header><p>{{summary}}</p><div v-if="enabled" class="measure-form"><slot/></div><EmptyState v-else title="措施未启用" description="启用后加入当前临时仿真配置"/></article></template>
