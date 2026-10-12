<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { weatherApi } from "@/api/weather";
import { marketDataApi } from "@/api/marketData";
import type { Site, WeatherSite } from "@/types";
const props = defineProps<{ site: Site }>();
const sites = ref<WeatherSite[]>([]),
  weather = reactive({
    name: "",
    latitude: null as number | null,
    longitude: null as number | null,
    timezone: props.site.timezone,
    source: "FILE",
  }),
  contract = reactive({
    name: "绿电合同",
    start_at: "",
    end_at: "",
    purchase_kwh: null as number | null,
    purchase_share: null as number | null,
    emission_factor_kg_per_kwh: 0,
    premium_per_kwh: 0,
    status: "ACTIVE",
    source: "MANUAL",
  });
async function createWeather() {
  try {
    const row = await weatherApi.createSite({
      enterprise_id: props.site.enterprise_id,
      ...weather,
    });
    sites.value.push(row);
    ElMessage.success("气象站点创建成功，可开始气象数据导入");
  } catch (e) {
    ElMessage.error((e as { message?: string }).message || "创建失败");
  }
}
async function createContract() {
  try {
    await marketDataApi.createContract({
      enterprise_id: props.site.enterprise_id,
      ...contract,
    });
    ElMessage.success("绿电合同已保存");
  } catch (e) {
    ElMessage.error((e as { message?: string }).message || "保存失败");
  }
}
onMounted(
  async () => (sites.value = await weatherApi.sites(props.site.enterprise_id)),
);
</script>
<template>
  <div class="setup-columns">
    <div class="setup-form">
      <h3>气象数据配置</h3>
      <el-input
        v-model="weather.name"
        placeholder="气象站点名称"
      /><el-input-number
        v-model="weather.longitude"
        placeholder="经度"
      /><el-input-number
        v-model="weather.latitude"
        placeholder="纬度"
      /><el-input
        v-model="weather.timezone"
        placeholder="IANA 时区"
      /><el-button @click="createWeather">创建气象站点</el-button
      ><span>现有站点：{{ sites.length }}</span>
    </div>
    <div class="setup-form">
      <h3>绿电合同</h3>
      <el-alert
        title="绿电合同是碳属性/市场配置，不是物理发电设备"
        type="info"
        :closable="false"
      /><el-input
        v-model="contract.name"
        placeholder="合同名称"
      /><el-date-picker
        v-model="contract.start_at"
        type="datetime"
        value-format="YYYY-MM-DDTHH:mm:ssZ"
        placeholder="开始时间"
      /><el-date-picker
        v-model="contract.end_at"
        type="datetime"
        value-format="YYYY-MM-DDTHH:mm:ssZ"
        placeholder="结束时间"
      /><el-input-number
        v-model="contract.purchase_share"
        :min="0.0001"
        :max="1"
        :step="0.01"
        placeholder="绿电比例"
      /><el-input-number
        v-model="contract.purchase_kwh"
        :min="0.01"
        placeholder="合同总量 kWh"
      /><el-input-number
        v-model="contract.emission_factor_kg_per_kwh"
        :min="0"
        placeholder="kgCO₂e/kWh"
      /><el-input-number
        v-model="contract.premium_per_kwh"
        :min="0"
        placeholder="溢价/kWh"
      /><el-button type="primary" @click="createContract"
        >保存绿电合同</el-button
      >
    </div>
  </div>
</template>
