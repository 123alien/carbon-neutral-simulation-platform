<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import { importsApi, type ImportKind } from "@/api/imports";
import FieldMappingEditor, { type MappingRow } from "./FieldMappingEditor.vue";
import ImportPreviewView from "./ImportPreview.vue";
import type { ImportPreview, WeatherSite } from "@/types";
const props = defineProps<{
  enterpriseId: number;
  weatherSites: WeatherSite[];
  allowedKinds?: ImportKind[];
}>();
const emit = defineEmits<{ confirmed: [] }>();
const kind = ref<ImportKind>("LOAD"),
  file = ref<File>(),
  report = ref<ImportPreview>(),
  busy = ref(false),
  timezone = ref("Asia/Shanghai"),
  weatherSiteId = ref<number>(),
  region = ref("全国"),
  version = ref("dynamic-v1");
const mappings = ref<MappingRow[]>([
  { source: "timestamp", target: "timestamp", unit: "", required: true },
  { source: "load", target: "load", unit: "kW", required: true },
]);
const kinds = computed<ImportKind[]>(() => props.allowedKinds || ["LOAD", "WEATHER", "PRICE", "GRID_FACTOR"]);
if (!kinds.value.includes(kind.value) && kinds.value[0]) kind.value = kinds.value[0];
const options = computed(() => {
  const map = Object.fromEntries(
    mappings.value
      .filter((x) => x.source && x.target)
      .map((x) => [x.target, x.source]),
  );
  if (kind.value === "LOAD")
    return {
      enterprise_id: props.enterpriseId,
      mapping: {
        timestamp: map.timestamp,
        load: map.load,
        irradiation: map.ghi_w_m2,
        temperature: map.temperature_c,
        humidity: map.humidity_pct,
      },
      load_unit: mappings.value.find((x) => x.target === "load")?.unit || "kW",
      timezone: timezone.value,
    };
  if (kind.value === "WEATHER")
    return {
      site_id: weatherSiteId.value,
      mapping: map,
      timezone: timezone.value,
    };
  if (kind.value === "PRICE")
    return {
      enterprise_id: props.enterpriseId,
      mapping: {
        timestamp: map.timestamp,
        purchase_price: map.purchase_price,
        feed_in_tariff: map.feed_in_tariff,
      },
      timezone: timezone.value,
    };
  return {
    region: region.value,
    version: version.value,
    mapping: { timestamp: map.timestamp, factor: map.factor },
    timezone: timezone.value,
  };
});
function choose(e: Event) {
  file.value = (e.target as HTMLInputElement).files?.[0];
  report.value = undefined;
}
async function preview() {
  if (!file.value) return ElMessage.warning("请选择 CSV/XLSX/XLSM 文件");
  busy.value = true;
  try {
    report.value = await importsApi.preview(
      kind.value,
      file.value,
      options.value,
    );
  } catch (e) {
    ElMessage.error((e as { message?: string }).message || "预览校验失败");
  } finally {
    busy.value = false;
  }
}
async function confirm() {
  if (!file.value || !report.value?.can_confirm) return;
  busy.value = true;
  try {
    const r = await importsApi.confirm(kind.value, file.value, options.value);
    ElMessage.success(`成功入库 ${r.inserted_rows} 行`);
    emit("confirmed");
  } catch (e) {
    ElMessage.error((e as { message?: string }).message || "Confirm 失败");
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div>
    <div class="setup-row">
      <el-select v-model="kind" @change="report = undefined"
        ><el-option v-if="kinds.includes('LOAD')" label="小时负荷" value="LOAD" /><el-option
          v-if="kinds.includes('WEATHER')" label="气象"
          value="WEATHER" /><el-option v-if="kinds.includes('PRICE')" label="电价" value="PRICE" /><el-option
          v-if="kinds.includes('GRID_FACTOR')" label="电网排放因子"
          value="GRID_FACTOR" /></el-select
      ><el-select
        v-if="kind === 'WEATHER'"
        v-model="weatherSiteId"
        placeholder="气象站点"
        ><el-option
          v-for="s in weatherSites"
          :key="s.id"
          :label="s.name"
          :value="s.id" /></el-select
      ><el-input
        v-if="kind === 'GRID_FACTOR'"
        v-model="region"
        placeholder="区域"
      /><el-input
        v-if="kind === 'GRID_FACTOR'"
        v-model="version"
        placeholder="因子版本"
      /><el-input v-model="timezone" placeholder="IANA 时区" /><input
        type="file"
        accept=".csv,.xlsx,.xlsm"
        @change="choose"
      />
    </div>
    <FieldMappingEditor v-model="mappings" />
    <div class="setup-actions">
      <el-button :loading="busy" @click="preview">预览并校验</el-button
      ><el-button
        type="primary"
        :loading="busy"
        :disabled="!report?.can_confirm"
        @click="confirm"
        >确认并入库</el-button
      ><span>预览阶段绝不写库</span>
    </div>
    <ImportPreviewView v-if="report" :report="report" />
  </div>
</template>
