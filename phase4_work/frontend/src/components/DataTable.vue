<script setup lang="ts">
import EmptyState from './EmptyState.vue'
export interface Column{key:string;label:string;width?:number;formatter?:(row:Record<string,unknown>)=>string}
defineProps<{rows:Record<string,unknown>[];columns:Column[];loading?:boolean}>()
</script>
<template><el-table :data="rows" v-loading="loading" class="base-table"><el-table-column v-for="col in columns" :key="col.key" :prop="col.key" :label="col.label" :width="col.width"><template v-if="col.formatter" #default="scope">{{col.formatter(scope.row)}}</template></el-table-column><template #empty><EmptyState/></template></el-table></template>
