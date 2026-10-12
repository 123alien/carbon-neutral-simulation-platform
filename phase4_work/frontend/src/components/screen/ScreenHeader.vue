<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { Site } from "@/types";
defineProps<{
  sites: Site[];
  siteId: number | null;
  backend: string;
  latest: string | null;
}>();
const emit = defineEmits<{ site: [number]; fullscreen: [] }>();
const now = ref(new Date()),
  fullscreen = ref(false);
let timer: number;
const clock = computed(() =>
    now.value.toLocaleString("zh-CN", { hour12: false }),
  ),
  syncFullscreen = () =>
    (fullscreen.value = Boolean(document.fullscreenElement));
onMounted(() => {
  timer = window.setInterval(() => (now.value = new Date()), 1000);
  document.addEventListener("fullscreenchange", syncFullscreen);
});
onBeforeUnmount(() => {
  clearInterval(timer);
  document.removeEventListener("fullscreenchange", syncFullscreen);
});
</script>
<template>
  <header class="screen-header">
    <div class="site-context">
      <el-select :model-value="siteId" @change="emit('site', $event)"
        ><el-option
          v-for="s in sites"
          :key="s.id"
          :value="s.id"
          :label="s.name" /></el-select
      ><span>{{ sites.find((x) => x.id === siteId)?.site_type || "--" }}</span>
    </div>
    <div class="screen-title">
      <small>CARBON NEUTRALITY SIMULATION</small>
      <h1>碳中和仿真推演综合管理平台</h1>
    </div>
    <div class="screen-clock">
      <b>{{ clock }}</b
      ><span
        >数据
        {{
          latest ? new Date(latest).toLocaleString("zh-CN") : "暂无更新"
        }}</span
      ><span>Backend {{ backend }}</span
      ><span>V1.0.0-beta.15</span
      ><button @click="emit('fullscreen')">
        {{ fullscreen ? "退出全屏" : "进入全屏" }}
      </button>
    </div>
  </header>
</template>
