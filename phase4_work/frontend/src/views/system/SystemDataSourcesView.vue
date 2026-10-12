<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useSiteStore } from "@/stores/site";
import { dataSourcesApi } from "@/api/dataSources";
import { sitesApi } from "@/api/sites";
import PageHeader from "@/components/PageHeader.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import EmptyState from "@/components/EmptyState.vue";
import StatusTag from "@/components/StatusTag.vue";
import DataSourceWizard from "@/components/data-config/DataSourceWizard.vue";
import type { DataSource, DataSourceDetail, DataSourceRuntime, Site } from "@/types";
const sites = useSiteStore(),
  rows = ref<DataSource[]>([]),
  details = ref<Record<number, DataSourceDetail>>({}),
  loading = ref(true),
  error = ref<string | null>(null),
  creating = ref(false),
  drawer = ref(false),
  selected = ref<DataSourceDetail | null>(null),
  runtime = ref<DataSourceRuntime | null>(null),
  active = ref("runtime"),
  busy = ref(false),
  intervalMinutes = ref(60),
  enterpriseFilter = ref<number|null>(null),
  ownerEnterpriseId = ref<number|null>(null);
const allSites=ref<Site[]>([]),ownerSiteId=ref<number|null>(null),ownerSite=computed(()=>allSites.value.find(x=>x.id===ownerSiteId.value)||null);
let poll: number | undefined;
const typeLabel = (v: string) =>
  (
    ({
      FILE: "文件导入",
      REST_API: "REST API",
      MQTT: "MQTT 接入",
      THIRD_PARTY: "第三方系统",
      MANUAL: "人工录入",
    }) as Record<string, string>
  )[v] || v;
const fmt = (v?: string | null) =>
  v ? new Date(v).toLocaleString("zh-CN") : "暂无数据";
const mappingRows = computed(() =>
  Object.entries(selected.value?.mapping || {}).map(([target, source]) => ({
    source,
    target,
  })),
);
const filteredRows=computed(()=>enterpriseFilter.value===null?rows.value:rows.value.filter(x=>x.enterprise_id===enterpriseFilter.value));
const siteName=(enterpriseId:number)=>allSites.value.find(x=>x.enterprise_id===enterpriseId)?.name||`企业 #${enterpriseId}`;
async function load() {
  loading.value = true;
  error.value = null;
  try {
    await sites.loadSites();
    allSites.value=await sitesApi.list({scope:'ALL'});
    rows.value = await dataSourcesApi.list();
    details.value = Object.fromEntries(
      await Promise.all(
        rows.value.map(
          async (x) => [x.id, await dataSourcesApi.detail(x.id)] as const,
        ),
      ),
    );
  } catch (e) {
    error.value = (e as { message?: string }).message || "数据源加载失败";
  } finally {
    loading.value = false;
  }
}
async function refreshRuntime() {
  if (selected.value)
    runtime.value = await dataSourcesApi.runtime(selected.value.source.id);
}
async function open(row: DataSource) {
  selected.value =
    details.value[row.id] || (await dataSourcesApi.detail(row.id));
  runtime.value = await dataSourcesApi.runtime(row.id);
  intervalMinutes.value = runtime.value.interval_minutes || 60;
  active.value = "runtime";
  drawer.value = true;
  if (poll) clearInterval(poll);
  poll = window.setInterval(refreshRuntime, 7000);
}
async function operate(action: "test" | "sync" | "start" | "stop") {
  if (!selected.value) return;
  busy.value = true;
  const id = selected.value.source.id;
  try {
    if (action === "test") {
      const r = await dataSourcesApi.test(id);
      ElMessage.success(r.message);
    } else if (action === "sync") {
      const r = await dataSourcesApi.syncNow(id);
      ElMessage.success(
        `接收 ${r.extracted}，入库 ${r.inserted}，拒绝 ${r.quarantined}`,
      );
    } else if (action === "start") {
      if (selected.value.source.source_type === "REST_API")
        await dataSourcesApi.configure(id, {
          collection_mode: "INTERVAL",
          enabled: true,
          interval_minutes: intervalMinutes.value,
        });
      else await dataSourcesApi.start(id);
      ElMessage.success("自动采集已启动");
    } else {
      await dataSourcesApi.stop(id);
      ElMessage.success("自动采集已停止");
    }
    await refreshRuntime();
    await load();
  } catch (e) {
    ElMessage.error((e as { message?: string }).message || "操作失败");
  } finally {
    busy.value = false;
  }
}
async function removeSource(row:DataSource){
  try{
    await ElMessageBox.confirm(`确认删除数据源“${row.name}”？已有绑定设备或事实数据时，后端会拒绝删除以保护真实数据。`,`删除数据源`,{type:"warning",confirmButtonText:"确认删除",cancelButtonText:"取消"});
    busy.value=true;await dataSourcesApi.remove(row.id);if(selected.value?.source.id===row.id){drawer.value=false;selected.value=null;runtime.value=null}ElMessage.success("数据源已删除");await load()
  }catch(e){if(e==='cancel'||e==='close')return;ElMessage.error((e as {message?:string}).message||"删除失败") }finally{busy.value=false}
}
onMounted(load);
onBeforeUnmount(() => poll && clearInterval(poll));
</script>
<template>
  <section data-testid="system-data-sources-page">
    <PageHeader
      kicker="自动采集运行"
      title="数据源管理"
      description="REST 定时拉取与 MQTT 常驻订阅均由后端服务运行，状态每 7 秒刷新。"
      ><el-select v-model="enterpriseFilter" clearable placeholder="全部园区/单位" style="width:210px"><el-option v-for="site in sites.sites" :key="site.id" :label="site.name" :value="site.enterprise_id"/></el-select><el-button
        type="primary"
        :disabled="!sites.sites.length"
        @click="ownerSiteId=sites.currentSite?.id||allSites[0]?.id||null;ownerEnterpriseId=ownerSite?.enterprise_id||null;creating = true"
        >新增数据源</el-button
      ><el-button @click="load">刷新</el-button></PageHeader
    ><LoadingState v-if="loading" /><ErrorState
      v-else-if="error"
      :message="error"
      @retry="load"
    />
    <article v-else class="panel">
      <el-alert title="平台级页面：默认展示全部园区的数据源；顶部当前园区不会改变本列表。" type="info" :closable="false" style="margin-bottom:12px"/><el-table :data="filteredRows" empty-text="暂无数据源" @row-click="open"
        ><el-table-column label="所属园区/单位"><template #default="{row}">{{siteName(row.enterprise_id)}}</template></el-table-column><el-table-column prop="name" label="名称" /><el-table-column
          label="类型"
          ><template #default="{ row }">{{
            typeLabel(row.source_type)
          }}</template></el-table-column
        ><el-table-column label="采集模式"
          ><template #default="{ row }">{{
            row.collection_mode === "INTERVAL"
              ? `定时拉取 · ${row.interval_minutes} 分钟`
              : row.collection_mode === "PERSISTENT"
                ? "常驻订阅"
                : "手动"
          }}</template></el-table-column
        ><el-table-column label="自动采集"
          ><template #default="{ row }"
            ><StatusTag :status="row.schedule_enabled ? 'ACTIVE' : 'STOPPED'" />
            {{ row.schedule_enabled ? "已启用" : "已停止" }}</template
          ></el-table-column
        ><el-table-column label="最近同步"
          ><template #default="{ row }">{{
            fmt(row.last_sync_at)
          }}</template></el-table-column
        ><el-table-column label="绑定设备"
          ><template #default="{ row }">{{
            details[row.id]?.binding.device_count ?? "暂无数据"
          }}</template></el-table-column
        ><el-table-column label="安全"
          ><template #default="{ row }">{{
            details[row.id]?.security.transport
          }}</template></el-table-column
        ><el-table-column label="操作" width="180"
          ><template #default="{ row }"
            ><el-button link @click.stop="open(row)"
              >查看详情</el-button
            ><el-button link type="danger" :loading="busy" @click.stop="removeSource(row)">删除</el-button></template
          ></el-table-column
        ></el-table
      ><EmptyState v-if="!rows.length" title="暂无数据源" />
    </article>
    <el-drawer v-model="drawer" size="72%" title="数据源详情"
      ><template v-if="selected"
        ><div class="summary">
          <b>{{ selected.source.name }}</b
          ><span>{{ typeLabel(selected.source.source_type) }}</span
          ><StatusTag :status="runtime?.runtime_status || 'STOPPED'" /><span>{{
            runtime?.runtime_status || "STOPPED"
          }}</span>
        </div>
        <div
          v-if="['REST_API', 'MQTT'].includes(selected.source.source_type)"
          class="actions"
        >
          <template v-if="selected.source.source_type === 'REST_API'"
            ><span>采集周期</span
            ><el-select v-model="intervalMinutes" style="width: 130px"
              ><el-option
                v-for="x in [15, 30, 60, 360, 1440]"
                :key="x"
                :value="x"
                :label="`${x} 分钟`" /></el-select></template
          ><el-button
            type="primary"
            :loading="busy"
            @click="operate('start')"
            >{{
              selected.source.source_type === "MQTT"
                ? "启动监听"
                : "启动自动采集"
            }}</el-button
          ><el-button :loading="busy" @click="operate('stop')">{{
            selected.source.source_type === "MQTT" ? "停止监听" : "停止自动采集"
          }}</el-button
          ><el-button :loading="busy" @click="operate('sync')"
            >立即同步</el-button
          ><el-button :loading="busy" @click="operate('test')"
            >测试连接</el-button
          >
        </div>
        <el-tabs v-model="active"
          ><el-tab-pane label="采集运行状态" name="runtime"
            ><el-descriptions v-if="runtime" :column="2" border
              ><el-descriptions-item label="采集模式">{{
                runtime.collection_mode
              }}</el-descriptions-item
              ><el-descriptions-item label="状态"
                ><StatusTag :status="runtime.runtime_status" />
                {{ runtime.runtime_status }}</el-descriptions-item
              ><el-descriptions-item label="已连接 / 已订阅"
                >{{ runtime.connected ? "是" : "否" }} /
                {{ runtime.subscribed ? "是" : "否" }}</el-descriptions-item
              ><el-descriptions-item label="Topic">{{
                runtime.current_topic || "不适用"
              }}</el-descriptions-item
              ><el-descriptions-item label="上次成功">{{
                fmt(runtime.last_success_at)
              }}</el-descriptions-item
              ><el-descriptions-item label="增量采集">{{ runtime.incremental_mode === 'NONE' ? '未启用' : '时间窗口' }}</el-descriptions-item
              ><el-descriptions-item label="成功业务水位">{{ fmt(runtime.last_success_watermark) }}</el-descriptions-item
              ><el-descriptions-item label="当前窗口">{{ runtime.incremental_mode === 'NONE' ? '未启用' : `${fmt(runtime.current_window_start)} 至 ${fmt(runtime.current_window_end)}` }}</el-descriptions-item
              ><el-descriptions-item label="本轮分页">{{ runtime.pages_fetched }} 页 / {{ runtime.records_fetched }} 条</el-descriptions-item
              ><el-descriptions-item label="请求成功页 / 失败页">{{ runtime.successful_pages }} / {{ runtime.failed_page ?? '无' }}</el-descriptions-item
              ><el-descriptions-item label="幂等跳过">{{ runtime.duplicates_skipped }}</el-descriptions-item
              ><el-descriptions-item label="下次运行">{{
                fmt(runtime.next_run_at)
              }}</el-descriptions-item
              ><el-descriptions-item label="最近连接">{{
                fmt(runtime.last_connected_at)
              }}</el-descriptions-item
              ><el-descriptions-item label="最近断开">{{
                fmt(runtime.last_disconnected_at)
              }}</el-descriptions-item
              ><el-descriptions-item label="最近消息">{{
                fmt(runtime.last_message_at)
              }}</el-descriptions-item
              ><el-descriptions-item label="最近接收 / 入库 / 拒绝"
                >{{ runtime.last_received_count }} /
                {{ runtime.last_persisted_count }} /
                {{ runtime.last_rejected_count }}</el-descriptions-item
              ><el-descriptions-item label="累计接收 / 入库 / 拒绝"
                >{{ runtime.received_count }} / {{ runtime.persisted_count }} /
                {{ runtime.rejected_count }}</el-descriptions-item
              ><el-descriptions-item label="重连 / 丢弃"
                >{{ runtime.reconnect_count }} /
                {{ runtime.dropped_count }}</el-descriptions-item
              ><el-descriptions-item label="连续失败">{{
                runtime.consecutive_failures
              }}</el-descriptions-item
              ><el-descriptions-item label="最近错误">{{
                runtime.last_error || "无"
              }}</el-descriptions-item></el-descriptions
            >
            <h3>统一处理链</h3>
            <div class="flow">
              <span>自动接收</span><i>→</i><span>字段映射</span><i>→</i
              ><span>L1</span><i>→</i><span>L2</span><i>→</i><span>L3</span
              ><i>→</i><span>入库 / 隔离</span>
            </div></el-tab-pane
          ><el-tab-pane label="安全传输" name="security"
            ><el-descriptions :column="2" border
              ><el-descriptions-item label="传输">{{
                selected.security.transport
              }}</el-descriptions-item
              ><el-descriptions-item label="安全传输">{{
                selected.security.secure_transport_enabled === null
                  ? "不适用"
                  : selected.security.secure_transport_enabled
                    ? "已启用"
                    : "未启用"
              }}</el-descriptions-item
              ><el-descriptions-item label="TLS 校验">{{
                selected.security.tls_verification ? "启用" : "未启用或不适用"
              }}</el-descriptions-item
              ><el-descriptions-item label="凭证">{{
                selected.security.credentials_configured
                  ? "已配置（已脱敏）"
                  : "未配置"
              }}</el-descriptions-item></el-descriptions
            ></el-tab-pane
          ><el-tab-pane label="字段映射" name="mapping"
            ><el-table :data="mappingRows" empty-text="按标准字段同名读取"
              ><el-table-column
                prop="source"
                label="原始字段" /><el-table-column
                prop="target"
                label="标准字段" /></el-table></el-tab-pane
          ><el-tab-pane label="三级校验与隔离" name="validation"
            ><el-table
              :data="selected.validation_logs"
              empty-text="暂无异常记录"
              ><el-table-column
                prop="created_at"
                label="时间" /><el-table-column
                prop="validation_stage"
                label="级别" /><el-table-column
                prop="device_external_id"
                label="设备" /><el-table-column
                prop="code"
                label="类型" /><el-table-column
                prop="message"
                label="原因" /><el-table-column
                prop="disposition"
                label="处理" /></el-table></el-tab-pane></el-tabs></template></el-drawer
    ><el-dialog v-model="creating" title="新增数据源" width="760px"
      ><el-form-item label="所属园区"><el-select v-model="ownerSiteId" style="width:100%" @change="ownerEnterpriseId=ownerSite?.enterprise_id||null"><el-option v-for="site in allSites" :key="site.id" :label="site.name" :value="site.id"/></el-select></el-form-item><DataSourceWizard
        v-if="ownerEnterpriseId"
        :enterprise-id="ownerEnterpriseId"
        :site="ownerSite"
        @saved="
          () => {
            creating = false;
            load();
          }
        "
    /></el-dialog>
  </section>
</template>
<style scoped>
.summary,
.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.actions {
  padding: 12px;
  background: #f3f8f6;
  border-radius: 8px;
}
.flow {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.flow span {
  padding: 10px 14px;
  border: 1px solid #b9d8d0;
  border-radius: 8px;
}
.flow i {
  font-style: normal;
  color: #2d8a72;
}
</style>
