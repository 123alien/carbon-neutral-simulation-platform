<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type { EChartsOption } from "echarts";
import { sitesApi } from "@/api/sites";
import { dataSourcesApi } from "@/api/dataSources";
import { useRouter } from "vue-router";
import { useSiteStore } from "@/stores/site";
import PageHeader from "@/components/PageHeader.vue";
import StatCard from "@/components/StatCard.vue";
import EmptyState from "@/components/EmptyState.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import BaseChart from "@/components/BaseChart.vue";
import StatusTag from "@/components/StatusTag.vue";
import type { AcquisitionOverview, SiteOverview } from "@/types";
const store = useSiteStore();
const router = useRouter();
const loading = ref(true);
const error = ref<string | null>(null);
const overviews = ref<SiteOverview[]>([]);
const acquisition = ref<AcquisitionOverview | null>(null);
const totals = computed(() => ({
  sites: store.sites.length,
  buildings: overviews.value.reduce((n, x) => n + x.building_count, 0),
  devices: overviews.value.reduce((n, x) => n + x.device_count, 0),
  sources: overviews.value.reduce((n, x) => n + x.data_source_count, 0),
}));
const latestEnergy = computed(
  () =>
    overviews.value
      .filter((x) => x.latest_energy)
      .sort((a, b) =>
        String(b.latest_data_time).localeCompare(String(a.latest_data_time)),
      )[0]?.latest_energy || null,
);
const latestCarbon = computed(() => {
  const values = overviews.value
    .map((x) => x.latest_carbon_emission_t)
    .filter((x): x is number => x !== null);
  return values.length ? values.reduce((a, b) => a + b, 0) : null;
});
const chartOption = computed<EChartsOption>(() => {
  const rows = overviews.value.filter(
    (x) => x.latest_carbon_emission_t !== null,
  );
  return {
    grid: { left: 42, right: 20, top: 42, bottom: 34 },
    xAxis: { type: "category", data: rows.map((x) => x.site.name) },
    yAxis: { type: "value", name: "tCO₂e" },
    series: [
      {
        name: "最新碳排",
        type: "bar",
        barMaxWidth: 34,
        data: rows.map((x) => x.latest_carbon_emission_t),
        itemStyle: { color: "#2d8a72", borderRadius: [5, 5, 0, 0] },
      },
    ],
  };
});
async function load() {
  loading.value = true;
  error.value = null;
  try {
    await store.loadSites();
    const settled = await Promise.allSettled(
      store.sites.map((x) => sitesApi.overview(x.id)),
    );
    overviews.value = settled
      .filter(
        (x): x is PromiseFulfilledResult<SiteOverview> =>
          x.status === "fulfilled",
      )
      .map((x) => x.value);
    acquisition.value = store.currentSite
      ? await dataSourcesApi.overview(store.currentSite.enterprise_id)
      : null;
    if (settled.some((x) => x.status === "rejected") && !overviews.value.length)
      throw new Error("站点概览服务暂不可用");
  } catch (e) {
    error.value = (e as { message?: string }).message || "无法加载概览数据";
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>
<template>
  <section>
    <PageHeader
      kicker="OVERVIEW"
      title="综合概览"
      description="聚合园区业务对象、能源接入与碳排放状态，所有指标均来自平台实时接口。"
    >
      <el-button :loading="loading" @click="load"
        ><el-icon><Refresh /></el-icon>刷新数据</el-button
      >
    </PageHeader>
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <template v-else>
      <article class="panel acquisition-strip clickable" @click="router.push('/system/data-quality')">
        <div><span>数据接入状态</span><b>{{ acquisition ? `${acquisition.normal_source_count}/${acquisition.source_count} 个数据源已运行` : '暂无数据' }}</b></div>
        <div><span>最近 24 小时接收</span><b>{{ acquisition?.received_last_24h ?? '暂无数据' }}</b></div>
        <div><span>数据有效率</span><b>{{ acquisition?.quality_rate == null ? '暂无数据' : `${(acquisition.quality_rate*100).toFixed(1)}%` }}</b></div>
        <div><span>隔离记录</span><b>{{ acquisition?.quarantined ?? '暂无数据' }}</b></div>
        <el-button link type="primary">查看数据质量 →</el-button>
      </article>
      <div class="stat-grid">
        <StatCard
          label="园区 / 站点"
          :value="totals.sites"
          unit="个"
          hint="已纳入统一业务视图"
          tone="green"
          ><template #icon
            ><el-icon><OfficeBuilding /></el-icon></template
        ></StatCard>
        <StatCard
          label="建筑"
          :value="totals.sites ? totals.buildings : null"
          unit="栋"
          hint="关联站点的建筑对象"
          tone="blue"
          ><template #icon
            ><el-icon><School /></el-icon></template
        ></StatCard>
        <StatCard
          label="设备"
          :value="totals.sites ? totals.devices : null"
          unit="台"
          hint="复用既有设备台账"
          tone="amber"
          ><template #icon
            ><el-icon><Monitor /></el-icon></template
        ></StatCard>
        <StatCard
          label="数据源"
          :value="totals.sites ? totals.sources : null"
          unit="个"
          hint="REST、MQTT 与文件接入"
          tone="slate"
          ><template #icon
            ><el-icon><Connection /></el-icon></template
        ></StatCard>
      </div>
      <div class="dashboard-grid">
        <article class="panel chart-panel">
          <div class="panel-head">
            <div>
              <span>CARBON PROFILE</span>
              <h2>站点碳排概览</h2>
            </div>
            <StatusTag status="VALID" />
          </div>
          <BaseChart
            :option="chartOption"
            :empty="latestCarbon === null"
            height="340px"
          />
        </article>
        <article class="panel live-panel">
          <div class="panel-head">
            <div>
              <span>LIVE SNAPSHOT</span>
              <h2>最新业务数据</h2>
            </div>
          </div>
          <div class="metric-focus">
            <span>最新碳排放</span
            ><strong v-if="latestCarbon !== null"
              >{{ latestCarbon.toLocaleString() }} <small>tCO₂e</small></strong
            ><strong v-else class="muted">暂无数据</strong>
          </div>
          <div class="divider"></div>
          <template v-if="latestEnergy"
            ><div class="energy-time">
              {{ new Date(latestEnergy.timestamp).toLocaleString("zh-CN") }}
            </div>
            <div class="energy-list">
              <div v-for="item in latestEnergy.values" :key="item.metric">
                <span>{{ item.metric }}</span
                ><b
                  >{{ item.value.toLocaleString() }}
                  <small>{{ item.unit }}</small></b
                >
              </div>
            </div></template
          >
          <EmptyState
            v-else
            title="暂无最新能源数据"
            description="接入站点计量数据后自动显示"
          />
        </article>
      </div>
      <article class="panel site-panel">
        <div class="panel-head">
          <div>
            <span>SITE PORTFOLIO</span>
            <h2>站点运行概况</h2>
          </div>
          <span class="panel-note">{{ store.sites.length }} 个业务对象</span>
        </div>
        <div v-if="overviews.length" class="site-list">
          <div
            v-for="item in overviews"
            :key="item.site.id"
            class="site-row clickable"
            @click="
              store.selectSite(item.site);
              router.push({ path: '/data', query: { site: item.site.id } });
            "
          >
            <div class="site-identity">
              <div class="site-symbol">{{ item.site.name.slice(0, 1) }}</div>
              <div>
                <strong>{{ item.site.name }}</strong
                ><span>{{ item.site.code }} · {{ item.site.site_type }}</span>
              </div>
            </div>
            <div>
              <span>建筑</span><b>{{ item.building_count }}</b>
            </div>
            <div>
              <span>设备</span><b>{{ item.device_count }}</b>
            </div>
            <div
              class="carbon-link"
              @click.stop="
                store.selectSite(item.site);
                router.push({ path: '/carbon', query: { site: item.site.id } });
              "
            >
              <span>碳排管理</span
              ><b>{{
                item.latest_carbon_emission_t === null
                  ? "暂无数据"
                  : `${item.latest_carbon_emission_t.toLocaleString()} tCO₂`
              }}</b>
            </div>
            <div>
              <span>完整率</span
              ><b>{{
                item.data_completeness_rate === null
                  ? "暂无数据"
                  : `${(item.data_completeness_rate * 100).toFixed(1)}%`
              }}</b>
            </div>
            <div>
              <span>最近数据</span
              ><b>{{
                item.latest_data_time
                  ? new Date(item.latest_data_time).toLocaleString("zh-CN")
                  : "暂无数据"
              }}</b>
            </div>
            <StatusTag
              :status="item.data_status === 'OK' ? 'ACTIVE' : 'PENDING'"
            />
          </div>
        </div>
        <EmptyState v-else title="暂无站点数据" description="请先完成平台初始化">
          <router-link to="/park?create=site"><el-button type="primary">新增园区</el-button></router-link>
        </EmptyState>
      </article>
      <article class="panel simulation-panel">
        <div class="panel-head">
          <div>
            <span>RECENT SIMULATION</span>
            <h2>最近仿真任务</h2>
          </div>
        </div>
        <EmptyState
          title="暂无可展示任务"
          description="后端当前未提供仿真任务列表接口，本页不会伪造任务数据"
        />
      </article>
    </template>
  </section>
</template>
