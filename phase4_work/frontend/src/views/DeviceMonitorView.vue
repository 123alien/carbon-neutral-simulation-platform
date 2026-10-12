<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue';
import LiveDeviceDashboard from '@/components/data-config/LiveDeviceDashboard.vue';
</script>

<template>
  <section class="device-monitor-page">
    <PageHeader kicker="IOT · DEVICE MONITORING" title="设备监测" description="查看湖北经济学院环境传感器与能源管控电表的在线状态、实时读数及历史波动；所有卡片均展示真实采集数据。" />
    <LiveDeviceDashboard />
  </section>
</template>

<style scoped>
.device-monitor-page{min-width:0}
</style>
