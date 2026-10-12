<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { Device } from "@/types";
import { panoramaTypeName } from "@/utils/panoramaFormat";

const props = defineProps<{
  devices: Device[];
  anomalyCount?: number;
  siteId?: number;
}>();
const emit = defineEmits<{ device: [Device]; anomalies: [] }>();
const viewport = ref<HTMLElement | null>(null),
  paused = ref(false),
  interacting = ref(false);
const counts = computed(() =>
  props.devices.reduce(
    (a, d) => {
      const k =
        d.status === "ACTIVE"
          ? "运行"
          : d.status === "INACTIVE"
            ? "停用"
            : "异常";
      a[k]++;
      return a;
    },
    { 运行: 0, 停用: 0, 异常: 0 },
  ),
);
const sortedDevices = computed(() =>
  [...props.devices].sort(
    (a, b) => Number(b.status !== "ACTIVE") - Number(a.status !== "ACTIVE"),
  ),
);
let timer = 0;
onMounted(() => {
  timer = window.setInterval(() => {
    const el = viewport.value;
    if (
      !el ||
      paused.value ||
      interacting.value ||
      document.hidden ||
      el.scrollHeight <= el.clientHeight
    )
      return;
    el.scrollTop =
      el.scrollTop >= el.scrollHeight - el.clientHeight - 1
        ? 0
        : el.scrollTop + 1;
  }, 80);
});
onBeforeUnmount(() => window.clearInterval(timer));
watch(
  () => props.siteId,
  () => {
    if (viewport.value) viewport.value.scrollTop = 0;
  },
);
</script>

<template>
  <section class="visual-panel right-bottom">
    <div class="monitor-heading">
      <h2>设备与告警</h2>
      <button @click="paused = !paused" :aria-pressed="paused">
        {{ paused ? "继续滚动" : "暂停滚动" }}
      </button>
    </div>
    <div class="status-row">
      <span class="ok">运行 {{ counts.运行 }}</span
      ><span>停用 {{ counts.停用 }}</span
      ><span class="warn">异常 {{ counts.异常 }}</span>
    </div>
    <p class="monitor-hint">
      共 {{ devices.length }} 台 · 异常优先 · 悬停暂停 · 状态来自设备台账
    </p>
    <div
      ref="viewport"
      class="device-viewport"
      data-testid="device-monitor-scroll"
      @mouseenter="interacting = true"
      @mouseleave="interacting = false"
      @focusin="interacting = true"
      @focusout="interacting = false"
    >
      <div class="device-list">
        <button
          v-for="device in sortedDevices"
          :key="device.id"
          :title="device.name"
          @click="emit('device', device)"
        >
          <i :class="device.status === 'ACTIVE' ? 'ok' : 'warn'"></i
          ><span>{{ device.name }}</span
          ><small
            >{{ panoramaTypeName(device.device_type) }}<br />{{
              device.status === "ACTIVE"
                ? "运行"
                : device.status === "INACTIVE"
                  ? "停用"
                  : "异常"
            }}</small
          >
        </button>
      </div>
      <p v-if="!devices.length" class="monitor-hint">当前园区暂无设备</p>
    </div>
    <button v-if="anomalyCount" class="alert-line" @click="emit('anomalies')">
      发现 {{ anomalyCount }} 条数据异常，点击前往数据接入处理
    </button>
    <div v-else class="alert-line quiet">
      当前查询未发现数据异常 · 未接入独立告警事件流
    </div>
  </section>
</template>

<style scoped>
.right-bottom {
  display: flex;
  flex-direction: column;
  min-height: 0;
  clip-path: none;
}
.monitor-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.monitor-heading h2 {
  flex: 1;
}
.monitor-heading button {
  background: #123f50;
  border: 1px solid #28798c;
  color: #b8eff0;
  font-size: 11px;
  padding: 3px 8px;
  cursor: pointer;
}
.monitor-hint {
  font-size: 10px;
  color: #89b6c1;
  margin: 0 0 7px;
}
.device-viewport {
  flex: 1;
  min-height: 40px;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: #28798c transparent;
}
.device-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.device-list button {
  min-height: 37px;
  grid-template-columns: 7px minmax(0, 1fr) auto;
  font-size: 11px;
  padding: 7px 8px;
  flex-shrink: 0;
}
.device-list button span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.device-list button small {
  text-align: right;
  font-size: 10px;
}
.device-list button:focus-visible {
  outline: 1px solid #43e0ca;
}
.alert-line {
  flex-shrink: 0;
  line-height: 1.5;
  cursor: pointer;
  text-align: left;
  border: 0;
}
@media (min-width: 1301px) and (max-height: 850px) {
  .monitor-hint {
    font-size: 9px;
    margin-bottom: 4px;
  }
}
</style>
