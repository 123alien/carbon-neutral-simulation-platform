<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { useRoute } from "vue-router";
import { useSiteStore } from "@/stores/site";
import { sitesApi } from "@/api/sites";
import { enterprisesApi } from "@/api/enterprises";
import { buildingsApi } from "@/api/buildings";
import { energySystemsApi } from "@/api/energySystems";
import { devicesApi } from "@/api/devices";
import { meteringPointsApi } from "@/api/meteringPoints";
import PageHeader from "@/components/PageHeader.vue";
import LoadingState from "@/components/LoadingState.vue";
import ErrorState from "@/components/ErrorState.vue";
import EmptyState from "@/components/EmptyState.vue";
import StatusTag from "@/components/StatusTag.vue";
import type { Building, Device, EnergySystem, Enterprise, MeteringPoint } from "@/types";

const route=useRoute(),sites = useSiteStore(),
  loading = ref(true),
  error = ref<string | null>(null),
  tab = ref("sites");
const buildings = ref<Building[]>([]),
  systems = ref<EnergySystem[]>([]),
  devices = ref<Device[]>([]),
  meters = ref<MeteringPoint[]>([]);
const enterprises=ref<Enterprise[]>([]),dialog=ref<"site"|"building"|"system"|"device"|"meter"|null>(null),saving=ref(false);
const siteForm=reactive({enterprise_id:0,code:"",name:"",site_type:"PARK",address:"",area_m2:null as number|null,population:null as number|null,timezone:"Asia/Shanghai",status:"ACTIVE",metadata_json:{},organization_node_id:null,longitude:null,latitude:null,position_json:null,geometry_json:null});
const buildingForm=reactive({organization_node_id:null,code:"",name:"",building_type:"OFFICE",area_m2:null as number|null,floor_count:null as number|null,population:null as number|null,status:"ACTIVE",metadata_json:{},longitude:null,latitude:null,position_json:null,geometry_json:null});
const systemForm=reactive({building_id:null as number|null,code:"",name:"",system_type:"ELECTRICITY",status:"ACTIVE",metadata_json:{}});
const deviceForm=reactive({data_source_id:null,external_id:"",name:"",device_type:"ELECTRIC_METER",metadata_json:{},status:"ACTIVE",longitude:null,latitude:null,position_json:null,geometry_json:null});
const meterForm=reactive({building_id:null as number|null,energy_system_id:null as number|null,device_id:null as number|null,data_source_id:null,code:"",name:"",metric_type:"energy_kwh",energy_type:"ELECTRICITY",unit:"kWh",status:"ACTIVE",metadata_json:{}});
const labels:Record<string,string>={PARK:"产业园区",CAMPUS:"校园",PUBLIC_INSTITUTION:"公共机构",ENTERPRISE:"独立企业",STREET:"街区",OTHER:"其他",ELECTRICITY:"电网与供电",WATER:"水系统",GAS:"燃气系统",HEATING:"供热系统",COOLING:"制冷系统",PV:"分布式光伏",WIND:"风力发电",STORAGE:"储能",HVAC:"空调",LIGHTING:"照明",EV_CHARGING:"充电桩",ELECTRIC_METER:"电表",WATER_METER:"水表",GAS_METER:"燃气表",EV_CHARGER:"充电桩"};
const label=(value:string)=>labels[value]||value;
type CampusFloor={building_id:string;building_name:string;floor_id:string;floor_number:number;areas:Array<{area_id:string;area_name:string;area_type:string}>};
const campusFloors=computed<CampusFloor[]>(()=>buildings.value.flatMap((building)=>{
  const metadata=building.metadata_json as {building_id?:string;floors?:Array<{floor_id:string;floor_number:number;areas:Array<{area_id:string;area_name:string;area_type:string}>}>};
  return (metadata?.floors||[]).map((floor)=>({building_id:metadata.building_id||building.code,building_name:building.name,...floor}));
}));
async function load() {
  loading.value = true;
  error.value = null;
  try {
    await sites.loadSites();enterprises.value=await enterprisesApi.list();
    const id = sites.currentSite?.id;
    if (!id) {
      buildings.value = [];
      systems.value = [];
      devices.value = [];
      meters.value = [];
      return;
    }
    [buildings.value, systems.value, devices.value, meters.value] =
      await Promise.all([
        buildingsApi.list(id),
        energySystemsApi.list({ site_id: id }),
        devicesApi.bySite(id),
        meteringPointsApi.list({ site_id: id }),
      ]);
  } catch (e) {
    error.value = (e as { message?: string }).message || "基础对象加载失败";
  } finally {
    loading.value = false;
  }
}
async function save(){saving.value=true;try{let created;
  if(dialog.value==="site"){created=await sitesApi.create(siteForm as never);await sites.loadSites();sites.selectSite(created)}
  else {const site=sites.currentSite;if(!site)throw new Error("请先选择园区");
    if(dialog.value==="building")await buildingsApi.create(site.id,buildingForm as never);
    if(dialog.value==="system")await energySystemsApi.create({site_id:site.id,...systemForm} as never);
    if(dialog.value==="device")await devicesApi.create({enterprise_id:site.enterprise_id,...deviceForm} as never);
    if(dialog.value==="meter")await meteringPointsApi.create({site_id:site.id,...meterForm} as never);
  }dialog.value=null;await load();ElMessage.success("保存成功")
}catch(e){ElMessage.error((e as {message?:string}).message||"保存失败")}finally{saving.value=false}}
watch(() => sites.currentSite?.id, load);
onMounted(async()=>{await load();if(route.query.create==='site')dialog.value='site'});
</script>
<template>
  <section data-testid="system-objects-page">
    <PageHeader
      kicker="园区业务起点"
      title="园区管理"
      description="统一维护园区基础信息，以及园区内的建筑、能源系统、设备和计量点。"
      ><el-button type="primary" @click="dialog='site'"
        >新增园区</el-button
      ><el-button @click="load">刷新</el-button></PageHeader
    ><LoadingState v-if="loading" /><ErrorState
      v-else-if="error"
      :message="error"
      @retry="load"
    /><template v-else
      ><div class="context">
        <span>当前园区</span
        ><el-select
          :model-value="sites.currentSite?.id"
          @change="
            (id: number) =>
              sites.selectSite(sites.sites.find((x) => x.id === id) || null)
          "
          ><el-option
            v-for="s in sites.sites"
            :key="s.id"
            :label="s.name"
            :value="s.id"
        /></el-select>
      </div>
      <EmptyState
        v-if="!sites.sites.length"
        title="暂无基础对象"
        description="请先创建园区并维护基础信息" /><el-tabs
        v-else
        v-model="tab"
        class="panel"
        ><el-tab-pane label="园区基础信息" name="sites"
          ><el-table :data="sites.sites"
            ><el-table-column prop="code" label="编码" /><el-table-column
              prop="name"
              label="名称" /><el-table-column
              label="类型"><template #default="{row}">{{label(row.site_type)}}</template></el-table-column><el-table-column
              prop="timezone"
              label="时区" /><el-table-column label="状态"
              ><template #default="{ row }"
                ><StatusTag
                  :status="
                    row.status
                  " /></template></el-table-column></el-table></el-tab-pane
        ><el-tab-pane label="建筑" name="buildings"><el-button type="primary" class="object-add" @click="dialog='building'">新增建筑</el-button
          ><el-table :data="buildings" empty-text="暂无建筑"
            ><el-table-column prop="code" label="编码" /><el-table-column
              prop="name"
              label="名称" /><el-table-column
              prop="building_type"
              label="类型" /><el-table-column
              prop="area_m2"
              label="面积 m²" /></el-table></el-tab-pane
        ><el-tab-pane label="能源系统" name="systems"><el-button type="primary" class="object-add" @click="dialog='system'">新增能源系统</el-button
          ><el-table :data="systems" empty-text="暂无能源系统"
            ><el-table-column prop="code" label="编码" /><el-table-column
              prop="name"
              label="名称" /><el-table-column
              label="系统类型"><template #default="{row}">{{label(row.system_type)}}</template></el-table-column></el-table></el-tab-pane
        ><el-tab-pane label="设备" name="devices"><el-button type="primary" class="object-add" @click="dialog='device'">新增设备</el-button
          ><el-table :data="devices" empty-text="暂无设备"
            ><el-table-column
              prop="external_id"
              label="外部 ID" /><el-table-column
              prop="name"
              label="名称" /><el-table-column
              label="设备类型"><template #default="{row}">{{label(row.device_type)}}</template></el-table-column><el-table-column
              prop="data_source_id"
              label="关联数据源" /></el-table></el-tab-pane
        ><el-tab-pane label="计量点" name="meters"><el-button type="primary" class="object-add" @click="dialog='meter'">新增计量点</el-button
          ><el-table :data="meters" empty-text="暂无计量点"
            ><el-table-column prop="code" label="编码" /><el-table-column
              prop="name"
              label="名称" /><el-table-column
              prop="energy_type"
              label="能源类型" /><el-table-column
              prop="metric_type"
              label="指标" /><el-table-column
              prop="unit"
              label="单位" /></el-table></el-tab-pane
        ><el-tab-pane v-if="sites.currentSite?.site_type==='CAMPUS'" label="楼层与区域编码" name="campus-spatial"
          ><el-alert title="校园空间编码用于统一关联能源设备、计量点及未来脱敏行为事件；当前不生成视频或跨镜追踪数据。" type="info" :closable="false" class="spatial-note"/>
          <el-table :data="campusFloors" empty-text="当前校园尚未配置楼层和区域编码">
            <el-table-column prop="building_name" label="建筑" min-width="130"/>
            <el-table-column prop="building_id" label="建筑编码" min-width="240"/>
            <el-table-column prop="floor_number" label="楼层" width="80"/>
            <el-table-column prop="floor_id" label="楼层编码" min-width="260"/>
            <el-table-column label="区域编码" min-width="420"><template #default="{row}"><div class="area-code" v-for="area in row.areas" :key="area.area_id"><b>{{area.area_name}}</b><span>{{area.area_id}}</span></div></template></el-table-column>
          </el-table></el-tab-pane></el-tabs
    ></template>
    <el-dialog :model-value="dialog==='site'" title="新增园区" width="680px" @close="dialog=null"><el-form label-position="top" class="form-grid"><el-form-item label="所属企业或组织"><el-select v-model="siteForm.enterprise_id"><el-option v-for="e in enterprises" :key="e.id" :label="e.name" :value="e.id"/></el-select></el-form-item><el-form-item label="园区名称"><el-input v-model="siteForm.name"/></el-form-item><el-form-item label="园区编码"><el-input v-model="siteForm.code"/></el-form-item><el-form-item label="园区类型"><el-select v-model="siteForm.site_type"><el-option label="产业园区" value="PARK"/><el-option label="校园" value="CAMPUS"/><el-option label="公共机构" value="PUBLIC_INSTITUTION"/><el-option label="独立企业" value="ENTERPRISE"/><el-option label="街区" value="STREET"/><el-option label="其他" value="OTHER"/></el-select></el-form-item><el-form-item label="地址"><el-input v-model="siteForm.address"/></el-form-item><el-form-item label="时区"><el-input v-model="siteForm.timezone"/></el-form-item></el-form><template #footer><el-button @click="dialog=null">取消</el-button><el-button type="primary" :loading="saving" :disabled="!siteForm.enterprise_id||!siteForm.name||!siteForm.code" @click="save">创建园区</el-button></template></el-dialog>
    <el-dialog :model-value="dialog==='building'" title="新增建筑" width="620px" @close="dialog=null"><el-form label-position="top" class="form-grid"><el-form-item label="建筑名称"><el-input v-model="buildingForm.name"/></el-form-item><el-form-item label="建筑编码"><el-input v-model="buildingForm.code"/></el-form-item><el-form-item label="建筑类型"><el-input v-model="buildingForm.building_type" placeholder="例如办公楼、实验楼"/></el-form-item><el-form-item label="建筑面积"><el-input-number v-model="buildingForm.area_m2" :min="0"/></el-form-item><el-form-item label="楼层数"><el-input-number v-model="buildingForm.floor_count" :min="0"/></el-form-item></el-form><template #footer><el-button @click="dialog=null">取消</el-button><el-button type="primary" :loading="saving" :disabled="!buildingForm.name||!buildingForm.code" @click="save">保存</el-button></template></el-dialog>
    <el-dialog :model-value="dialog==='system'" title="新增能源系统" width="620px" @close="dialog=null"><el-form label-position="top" class="form-grid"><el-form-item label="系统名称"><el-input v-model="systemForm.name"/></el-form-item><el-form-item label="系统编码"><el-input v-model="systemForm.code"/></el-form-item><el-form-item label="系统类型"><el-select v-model="systemForm.system_type"><el-option v-for="v in ['ELECTRICITY','WATER','GAS','HEATING','COOLING','PV','WIND','STORAGE','HVAC','LIGHTING','EV_CHARGING','OTHER']" :key="v" :label="label(v)" :value="v"/></el-select></el-form-item><el-form-item label="所属建筑（可选）"><el-select v-model="systemForm.building_id" clearable><el-option v-for="b in buildings" :key="b.id" :label="b.name" :value="b.id"/></el-select></el-form-item></el-form><template #footer><el-button @click="dialog=null">取消</el-button><el-button type="primary" :loading="saving" :disabled="!systemForm.name||!systemForm.code" @click="save">保存</el-button></template></el-dialog>
    <el-dialog :model-value="dialog==='device'" title="新增设备" width="620px" @close="dialog=null"><el-form label-position="top" class="form-grid"><el-form-item label="设备名称"><el-input v-model="deviceForm.name"/></el-form-item><el-form-item label="设备编码"><el-input v-model="deviceForm.external_id"/></el-form-item><el-form-item label="设备类型"><el-select v-model="deviceForm.device_type"><el-option v-for="v in ['ELECTRIC_METER','WATER_METER','GAS_METER','PV','WIND','EV_CHARGER','STORAGE','HVAC','LIGHTING']" :key="v" :label="label(v)" :value="v"/></el-select></el-form-item></el-form><template #footer><el-button @click="dialog=null">取消</el-button><el-button type="primary" :loading="saving" :disabled="!deviceForm.name||!deviceForm.external_id" @click="save">保存</el-button></template></el-dialog>
    <el-dialog :model-value="dialog==='meter'" title="新增计量点" width="680px" @close="dialog=null"><el-form label-position="top" class="form-grid"><el-form-item label="计量点名称"><el-input v-model="meterForm.name"/></el-form-item><el-form-item label="计量点编码"><el-input v-model="meterForm.code"/></el-form-item><el-form-item label="关联设备"><el-select v-model="meterForm.device_id" clearable><el-option v-for="d in devices" :key="d.id" :label="d.name" :value="d.id"/></el-select></el-form-item><el-form-item label="关联能源系统"><el-select v-model="meterForm.energy_system_id" clearable><el-option v-for="s in systems" :key="s.id" :label="s.name" :value="s.id"/></el-select></el-form-item><el-form-item label="指标名称"><el-input v-model="meterForm.metric_type"/></el-form-item><el-form-item label="能源类型"><el-select v-model="meterForm.energy_type"><el-option v-for="v in ['ELECTRICITY','WATER','GAS','HEATING','COOLING']" :key="v" :label="label(v)" :value="v"/></el-select></el-form-item><el-form-item label="单位"><el-input v-model="meterForm.unit"/></el-form-item></el-form><template #footer><el-button @click="dialog=null">取消</el-button><el-button type="primary" :loading="saving" :disabled="!meterForm.name||!meterForm.code" @click="save">保存</el-button></template></el-dialog>
  </section>
</template>
<style scoped>
.context {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 16px;
}
.context .el-select {
  width: 280px;
}
.object-add{margin-bottom:12px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}.form-grid .el-select,.form-grid .el-input-number{width:100%}.spatial-note{margin-bottom:12px}.area-code{display:flex;gap:10px;line-height:1.8}.area-code b{min-width:84px;color:#215e4d}.area-code span{font-family:"JetBrains Mono","Consolas",monospace;color:#586963}
</style>
