<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type { EChartsOption } from "echarts";
import PageHeader from "@/components/PageHeader.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import BaseChart from "@/components/BaseChart.vue";
import { modelValidationApi } from "@/api/modelValidation";
import type { ModelValidationDetail } from "@/types";
const loading = ref(true),
  error = ref<string | null>(null),
  active = ref<"WIND" | "PV">("WIND"),
  details = ref<Record<string, ModelValidationDetail>>({});
const current = computed(() => details.value[active.value]);
const n = (v: number, d = 2) =>
  v.toLocaleString("zh-CN", { maximumFractionDigits: d });
const chart = computed<EChartsOption>(() => {
  const rows = current.value?.series || [];
  return {
    tooltip: { trigger: "axis" },
    legend: { data: ["实测功率", "改进前仿真", "改进后仿真"] },
    grid: { left: 70, right: 25, top: 55, bottom: 70 },
    xAxis: {
      type: "category",
      data: rows.map((x) => new Date(x.timestamp).toLocaleString("zh-CN")),
    },
    yAxis: { type: "value", name: "kW" },
    series: [
      {
        name: "实测功率",
        type: "line",
        showSymbol: false,
        data: rows.map((x) => x.observed_power_kw),
      },
      {
        name: "改进前仿真",
        type: "line",
        showSymbol: false,
        data: rows.map((x) => x.legacy_simulated_power_kw),
      },
      {
        name: "改进后仿真",
        type: "line",
        showSymbol: false,
        data: rows.map((x) => x.simulated_power_kw),
      },
    ],
  };
});
async function load() {
  loading.value = true;
  error.value = null;
  try {
    const [wind, pv] = await Promise.all([
      modelValidationApi.detail("WIND"),
      modelValidationApi.detail("PV"),
    ]);
    details.value = { WIND: wind, PV: pv };
  } catch (e) {
    error.value = (e as { message?: string }).message || "模型验证数据加载失败";
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section data-testid="model-validation-page">
    <PageHeader
      kicker="模型验证中心"
      title="实测与仿真对比"
      description="公开验证数据仅在此处展示，不进入正式园区业务列表；校准数据与留出验证数据严格分离。"
      ><el-button @click="load">刷新</el-button></PageHeader
    ><LoadingState v-if="loading" /><ErrorState
      v-else-if="error"
      :message="error"
      @retry="load"
    /><template v-else-if="current"
      ><el-tabs v-model="active"
        ><el-tab-pane label="风电" name="WIND" /><el-tab-pane
          label="光伏"
          name="PV" /></el-tabs
      ><el-alert
        v-if="current.fallback_used"
        :title="`${current.fallback_code}：部分参数仍使用模型默认或校准值，不能解释为真实设备参数。`"
        type="warning"
        :closable="false"
        show-icon
      />
      <div class="summary-grid">
        <article>
          <span>数据集</span><b>{{ current.dataset }}</b>
        </article>
        <article>
          <span>模型版本</span><b>{{ current.model_version }}</b>
        </article>
        <article>
          <span>验证时间范围</span><b>{{ current.time_range }}</b>
        </article>
        <article>
          <span>数据类别</span><b>{{ current.data_class }}</b>
        </article>
      </div>
      <article class="panel">
        <h2>实测与仿真功率曲线</h2>
        <BaseChart :option="chart" />
      </article>
      <article class="panel">
        <h2>改进前后指标（同一留出集）</h2>
        <el-table
          :data="[
            { label: '改进前', ...current.metrics.before },
            { label: '改进后', ...current.metrics.after },
          ]"
          ><el-table-column prop="label" label="版本" /><el-table-column
            label="实测总能量"
            ><template #default="{ row }"
              >{{ n(row.observed_energy_kwh) }} kWh</template
            ></el-table-column
          ><el-table-column label="仿真总能量"
            ><template #default="{ row }"
              >{{ n(row.simulated_energy_kwh) }} kWh</template
            ></el-table-column
          ><el-table-column label="MAE"
            ><template #default="{ row }"
              >{{ n(row.mae_kw) }} kW</template
            ></el-table-column
          ><el-table-column label="RMSE"
            ><template #default="{ row }"
              >{{ n(row.rmse_kw) }} kW</template
            ></el-table-column
          ><el-table-column label="nRMSE"
            ><template #default="{ row }"
              >{{
                n(row.nrmse_pct_rated ?? row.nrmse_pct_of_dc_capacity)
              }}%</template
            ></el-table-column
          ><el-table-column label="Energy Error"
            ><template #default="{ row }"
              >{{ n(row.energy_error_pct) }}%</template
            ></el-table-column
          ><el-table-column label="Correlation"
            ><template #default="{ row }">{{
              n(row.correlation, 4)
            }}</template></el-table-column
          ></el-table
        >
      </article>
      <div class="two">
        <article class="panel">
          <h2>参数来源</h2>
          <el-table
            :data="
              Object.entries(current.parameter_sources).map(
                ([name, value]) => ({ name, ...value }),
              )
            "
            ><el-table-column prop="name" label="参数" /><el-table-column
              prop="value"
              label="值" /><el-table-column label="来源类别"
              ><template #default="{ row }"
                ><el-tag
                  :type="
                    row.class === 'REAL_METADATA'
                      ? 'success'
                      : row.class === 'CALIBRATED'
                        ? 'warning'
                        : 'info'
                  "
                  >{{ row.class }}</el-tag
                ></template
              ></el-table-column
            ><el-table-column prop="source" label="来源"
          /></el-table>
        </article>
        <article class="panel">
          <h2>限制说明</h2>
          <ul>
            <li v-for="item in current.limitations" :key="item">{{ item }}</li>
          </ul>
          <p>实测值来自公开观测；仿真值来自模型输出，两者不会互相覆盖。</p>
        </article>
      </div></template
    >
  </section>
</template>
<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin: 14px 0;
}
.summary-grid article {
  padding: 15px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.summary-grid span {
  font-size: 11px;
  color: #71837d;
}
.summary-grid b {
  color: #24463e;
}
.panel {
  margin-top: 14px;
}
.two {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 14px;
}
.two li,
.two p {
  color: #61736e;
  font-size: 12px;
  line-height: 1.8;
}
@media (max-width: 1000px) {
  .summary-grid,
  .two {
    grid-template-columns: 1fr;
  }
}
</style>
