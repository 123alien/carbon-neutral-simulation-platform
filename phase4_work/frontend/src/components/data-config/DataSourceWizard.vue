<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { dataSourcesApi } from "@/api/dataSources";
import type { Building, DataSource, DataSourceCreate, Device, MeteringPoint, Site } from "@/types";
const props = defineProps<{ enterpriseId: number; site?:Site|null; buildings?:Building[]; devices?:Device[]; meters?:MeteringPoint[] }>();
const emit = defineEmits<{ saved: [DataSource] }>();
const step = ref(0),
  busy = ref(false),
  form = reactive<DataSourceCreate>({
    enterprise_id: props.enterpriseId,
    site_id: props.site?.id ?? null,
    building_id: null,
    device_id: null,
    metering_point_id: null,
    data_nature: "MEASURED",
    name: "",
    source_type: "FILE",
    status: "ACTIVE",
    config_json: { timezone: "Asia/Shanghai", api_timezone:"UTC", purpose: "HOURLY_LOAD", verify_tls: true, incremental_mode:"NONE",pagination_mode:"NONE",time_format:"iso8601",overlap_minutes:10,next_path:"_links.next.href",max_pages:100,validation_levels: ["L1","L2","L3"], field_mapping: {} },
    credentials: null,
  }),
  secret = reactive({ username: "", password: "", token: "", client_key: "" });
const config = computed(() => form.config_json as Record<string, unknown>);
async function save() {
  busy.value = true;
  try {
    form.enterprise_id = props.enterpriseId;
    form.site_id = props.site?.id ?? form.site_id;
    form.credentials =
      Object.fromEntries(Object.entries(secret).filter(([, v]) => v)) || null;
    const row = await dataSourcesApi.create(form);
    ElMessage.success("数据源已保存，敏感凭证不会回显");
    emit("saved", row);
  } catch (e) {
    ElMessage.error((e as { message?: string }).message || "保存失败");
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="source-wizard">
    <el-steps :active="step" finish-status="success"
      ><el-step title="基础信息" /><el-step title="连接配置" /><el-step
        title="字段与校验" /><el-step title="保存"
    /></el-steps>
    <div v-if="step === 0" class="setup-form">
      <el-alert title="数据源是数据入口，必须明确关联到园区，并可进一步关联建筑、设备或计量点。" type="info" :closable="false" />
      <el-input v-model="form.name" placeholder="数据源名称" /><el-select
        v-model="form.source_type"
        ><el-option
          v-for="t in [{value:'FILE',label:'文件导入'},{value:'REST_API',label:'REST API'},{value:'MQTT',label:'MQTT 接入'},{value:'THIRD_PARTY',label:'第三方系统'},{value:'MANUAL',label:'人工录入'}]"
          :key="t.value"
          :value="t.value"
          :label="t.label"
      /></el-select>
      <el-select v-model="form.site_id" placeholder="所属园区" :disabled="Boolean(props.site)"><el-option v-if="props.site" :label="props.site.name" :value="props.site.id"/></el-select>
      <el-select v-model="form.building_id" clearable placeholder="关联建筑（可选）"><el-option v-for="item in props.buildings||[]" :key="item.id" :label="item.name" :value="item.id"/></el-select>
      <el-select v-model="form.device_id" clearable placeholder="关联设备（可选）"><el-option v-for="item in props.devices||[]" :key="item.id" :label="item.name" :value="item.id"/></el-select>
      <el-select v-model="form.metering_point_id" clearable placeholder="关联计量点（可选）"><el-option v-for="item in props.meters||[]" :key="item.id" :label="item.name" :value="item.id"/></el-select>
    </div>
    <div v-else-if="step === 1" class="setup-form">
      <template v-if="form.source_type === 'FILE'"
        ><el-select v-model="form.data_nature" placeholder="数据性质"><el-option label="实测数据" value="MEASURED"/><el-option label="仿真数据" value="SIMULATED"/><el-option label="历史数据" value="HISTORICAL"/></el-select><el-select v-model="config.purpose"
          ><el-option label="小时负荷" value="HOURLY_LOAD" /><el-option
            label="气象"
            value="WEATHER" /><el-option label="电价" value="PRICE" /><el-option
            label="电网排放因子"
            value="GRID_FACTOR" /><el-option
            label="设备指标"
            value="DEVICE_METRIC" /></el-select
        ><el-input v-model="config.timezone" placeholder="IANA 时区" /><el-input
          v-model="config.default_unit"
          placeholder="默认单位" /></template
      ><template
        v-else-if="
          form.source_type === 'REST_API' || form.source_type === 'THIRD_PARTY'
        "
        ><el-input
          v-model="config.url"
          placeholder="HTTPS 接口地址" /><el-select
          v-model="config.method"
          placeholder="请求方式"
          ><el-option label="GET" value="GET" /><el-option
            label="POST"
            value="POST" /></el-select
        ><el-input-number v-model="config.timeout_seconds" :min="1" /><el-switch v-model="config.verify_tls" active-text="校验 TLS 证书"/><el-input
          v-model="secret.username"
          autocomplete="off"
          placeholder="用户名（仅输入）" /><el-input
          v-model="secret.password"
          type="password"
          show-password
          autocomplete="new-password"
          placeholder="密码（不回显）" /><el-input
          v-model="secret.token"
          type="password"
          show-password
          autocomplete="new-password"
          placeholder="Token（不回显）" />
        ><el-collapse class="advanced-rest"><el-collapse-item title="高级：增量采集与分页" name="incremental"><div class="mapping-grid">
          <label><span>增量采集</span><el-select v-model="config.incremental_mode"><el-option label="不启用" value="NONE"/><el-option label="时间窗口" value="TIME_WINDOW"/></el-select></label>
          <label><span>分页方式</span><el-select v-model="config.pagination_mode"><el-option label="不分页" value="NONE"/><el-option label="Next 链接分页" value="LINK_NEXT"/></el-select></label>
          <template v-if="config.incremental_mode==='TIME_WINDOW'"><label><span>起始参数名</span><el-input v-model="config.start_param" placeholder="例如 start_time"/></label><label><span>结束参数名</span><el-input v-model="config.end_param" placeholder="例如 end_time"/></label><label><span>首次采集起点</span><el-input v-model="config.initial_start" placeholder="ISO 8601，首次运行必填"/></label><label><span>时间格式</span><el-input v-model="config.time_format" placeholder="iso8601 或 strftime"/></label><label><span>接口时区</span><el-input v-model="config.api_timezone" placeholder="例如 UTC / Asia/Shanghai"/></label><label><span>重叠窗口（分钟）</span><el-input-number v-model="config.overlap_minutes" :min="0" :max="60"/></label></template>
          <template v-if="config.pagination_mode==='LINK_NEXT'"><label><span>Next 字段路径</span><el-input v-model="config.next_path" placeholder="_links.next.href"/></label><label><span>最大页数</span><el-input-number v-model="config.max_pages" :min="1" :max="1000"/></label><label><span>单轮最大记录数</span><el-input-number v-model="config.max_records_per_run" :min="1"/></label></template>
          <label><span>外部记录 ID 字段</span><el-input v-model="config.source_record_id_path" placeholder="例如 id / sessionID / uuid"/></label>
        </div><el-alert title="时间窗口内部按 UTC 保存；重叠数据由外部记录 ID 优先幂等，无外部 ID 时使用设备、时间和指标去重。" type="info" :closable="false"/></el-collapse-item></el-collapse></template
      ><template v-else-if="form.source_type === 'MQTT'"
        ><el-input
          v-model="config.host"
          placeholder="Broker host" /><el-input-number
          v-model="config.port"
          :min="1"
          :max="65535" /><el-input
          v-model="config.topic"
          placeholder="Topic" /><el-switch
          v-model="config.tls"
          active-text="TLS（推荐）" /><el-input
          v-model="secret.username"
          placeholder="Username" /><el-input
          v-model="secret.password"
          type="password"
          autocomplete="new-password"
          placeholder="Password（不回显）" /><el-input
          v-model="secret.client_key"
          type="password"
          autocomplete="new-password"
          placeholder="Client key（不回显）" /></template
      ><el-alert
        v-else
        title="MANUAL 适合少量标准记录，不用于大规模数据编辑"
        type="info"
        :closable="false"
      />
    </div>
    <div v-else-if="step === 2">
      <el-alert v-if="['REST_API','THIRD_PARTY','MQTT'].includes(form.source_type)" :title="form.source_type==='MQTT'?'支持常驻订阅与自动重连，需在保存后启用':'REST API 支持手动或定时采集；启用时间窗口后两者遵守同一 watermark'" type="info" :closable="false" show-icon/>
      <h4>数据提取与字段映射</h4>
      <div class="mapping-grid">
        <label v-for="field in ['device_external_id','device_name','device_type','timestamp','metric_name','value','unit','source_record_id']" :key="field"><span>{{field}}</span><el-input v-model="(config.field_mapping as Record<string,string>)[field]" :placeholder="`原始字段名（默认 ${field}）`"/></label>
      </div>
      <el-checkbox-group v-model="config.validation_levels"
        ><el-checkbox value="L1">L1 结构校验</el-checkbox
        ><el-checkbox value="L2">L2 语义/范围校验</el-checkbox
        ><el-checkbox value="L3">L3 时序校验</el-checkbox></el-checkbox-group
      >
      <p>
        后端将执行必填、单位、范围、时间戳、重复、未来时间及变化率校验；不可配置规则仅按后端定义执行。
      </p>
    </div>
    <div v-else>
      <el-descriptions border :column="1"
        ><el-descriptions-item label="名称">{{
          form.name
        }}</el-descriptions-item
        ><el-descriptions-item label="类型">{{
          ({FILE:'文件',REST_API:'接口',MQTT:'物联网',THIRD_PARTY:'第三方系统',MANUAL:'人工录入'} as Record<string,string>)[form.source_type]
        }}</el-descriptions-item
        ><el-descriptions-item v-if="form.source_type==='FILE'" label="数据性质">{{({MEASURED:'实测数据',SIMULATED:'仿真数据',HISTORICAL:'历史数据'} as Record<string,string>)[form.data_nature||'MEASURED']}}</el-descriptions-item
        ><el-descriptions-item label="凭证">{{
          Object.values(secret).some(Boolean) ? "********" : "未配置"
        }}</el-descriptions-item></el-descriptions
      >
    </div>
    <div class="setup-actions">
      <el-button :disabled="step === 0" @click="step--">上一步</el-button
      ><el-button v-if="step < 3" type="primary" @click="step++"
        >下一步</el-button
      ><el-button v-else type="primary" :loading="busy" @click="save"
        >保存</el-button
      >
    </div>
  </div>
</template>
<style scoped>.mapping-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0}.mapping-grid label{display:flex;flex-direction:column;gap:5px}.mapping-grid span{font-size:12px;color:#65736f}.advanced-rest{grid-column:1/-1;width:100%}</style>
