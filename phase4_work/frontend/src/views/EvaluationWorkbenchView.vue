<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useSiteStore } from "@/stores/site";
import PageHeader from "@/components/PageHeader.vue";
const route = useRoute(),
  router = useRouter(),
  sites = useSiteStore();
const query = computed(() => ({
  scenario_version: route.query.scenario_version,
  task: route.query.task,
}));
</script>
<template>
  <section>
    <PageHeader
      kicker="ASSESSMENT WORKBENCH"
      title="评估与报告工作台"
      description="以同一场景版本和仿真任务串联碳市场、风险与正式报告。"
    />
    <div class="business-context">
      <span
        >当前 Site：<b>{{ sites.currentSite?.name || "未选择" }}</b></span
      ><span
        >ScenarioVersion：<b>{{
          route.query.scenario_version || "未选择"
        }}</b></span
      ><span
        >SimulationTask：<b>{{ route.query.task || "未选择" }}</b></span
      >
    </div>
    <div class="evaluation-grid">
      <article class="panel">
        <h2>碳市场评估</h2>
        <p>配额、碳价、CCER、绿证和综合碳成本。</p>
        <el-tooltip :disabled="Boolean(query.scenario_version&&query.task)" content="请先选择场景版本和仿真任务"><span><el-button :disabled="!query.scenario_version||!query.task" @click="router.push({path:'/carbon-market',query})">进入碳市场分析</el-button></span></el-tooltip>
      </article>
      <article class="panel">
        <h2>风险评估</h2>
        <p>六类风险、触发原因及实施建议。</p>
        <el-tooltip :disabled="Boolean(query.scenario_version&&query.task)" content="请先选择场景版本和仿真任务"><span><el-button :disabled="!query.scenario_version||!query.task" @click="router.push({path:'/risks',query})">进入风险分析</el-button></span></el-tooltip>
      </article>
      <article class="panel">
        <h2>正式报告</h2>
        <p>基于不可变快照生成、预览和下载 DOCX/PDF。</p>
        <el-tooltip :disabled="Boolean(query.scenario_version&&query.task)" content="暂无可用于报告的仿真任务"><span><el-button type="primary" :disabled="!query.scenario_version||!query.task" @click="router.push({path:'/reports',query})">创建、预览与下载报告</el-button></span></el-tooltip>
      </article>
    </div>
  </section>
</template>
