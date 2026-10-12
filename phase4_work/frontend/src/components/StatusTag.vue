<script setup lang="ts">import {computed} from 'vue';const props=defineProps<{status:string}>();const type=computed(()=>({SUCCESS:'success',ACTIVE:'success',VALID:'success',GENERATING:'warning',PENDING:'info',FAILED:'danger',HIGH:'danger',MEDIUM:'warning',LOW:'success'}[props.status]||'info'));</script>
<template><el-tag :type="type" effect="light" round>{{status}}</el-tag></template>
