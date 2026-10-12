import { test, expect } from "@playwright/test";

test("侧栏真实折叠并恢复", async ({ page }) => {
  await page.goto("/dashboard");
  const aside = page.locator(".sidebar");
  await expect(aside).toHaveCSS("width", "248px");
  await page.getByTestId("sidebar-toggle").click();
  await expect(aside).toHaveCSS("width", "72px");
  await page.getByTestId("sidebar-toggle").click();
  await expect(aside).toHaveCSS("width", "248px");
});

test("管理员菜单的系统、关于和版本动作都可达", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByTestId("admin-menu").click();
  await page.getByText("关于平台", { exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("碳中和仿真推演平台");
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();

  await page.getByTestId("admin-menu").click();
  await page.getByText("版本信息", { exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("V1.0.0-beta.15");
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();

  await page.reload();
  await page.getByTestId("admin-menu").click();
  await page.locator(".el-dropdown-menu:visible").getByRole("menuitem", { name: "系统设置 / 运行状态", exact: true }).click();
  await expect(page).toHaveURL(/\/system$/);
});

test("业务页签打开切换和关闭", async ({ page }) => {
  await page.goto("/carbon");
  await expect(page.locator(".work-tabs")).toContainText("碳核算");
  await page.goto("/carbon-neutral-simulation");
  await expect(page.locator(".work-tabs")).toContainText("碳中和仿真");
  await page.getByLabel("关闭 碳中和仿真").click();
  await expect(page).not.toHaveURL(/\/carbon-neutral-simulation$/);
});

test("旧初始化地址重定向到园区管理", async ({ page }) => {
  await page.goto("/data?setup=1");
  await expect(page).toHaveURL(/\/park\?create=site$/);
  await expect(page.getByRole("dialog",{name:"新增园区"})).toBeVisible();
});

test("主要工作台在真实浏览器中可访问且不白屏", async ({ page }) => {
  const routes = [
    "/dashboard",
    "/data",
    "/carbon",
    "/simulation",
    "/recommendations",
    "/scenarios",
    "/carbon-market",
    "/risks",
    "/reports",
    "/workbench/evaluation",
    "/system",
  ];
  for (const route of routes) {
    await page.goto(route);
    await expect(page.locator("#app")).not.toBeEmpty();
    if (route === "/3d") {
      await expect(page.locator('[data-testid="panorama-screen"]')).toBeVisible();
      await expect(page.locator(".sidebar")).toHaveCount(0);
    } else {
      await expect(page.locator(".sidebar")).toBeVisible();
      await expect(page.locator("main.el-main.main")).toBeVisible();
    }
  }
});

test("八个一级菜单按园区业务逻辑组织", async ({ page }) => {
  const entries = [
    { menu: "综合首页", url: /\/dashboard$/, title: "综合首页" },
    { menu: "园区管理", url: /\/park$/, title: "园区管理" },
    { menu: "数据接入", url: /\/data$/, title: "数据接入" },
    { menu: "碳核算", url: /\/carbon$/, title: "碳核算" },
    { menu: "3D全景", url: /\/3d$/, title: "3D全景" },
    { menu: "碳中和仿真", url: /\/carbon-neutral-simulation$/, title: "碳中和仿真" },
    { menu: "碳市场", url: /\/carbon-market$/, title: "碳市场" },
    { menu: "报告中心", url: /\/reports$/, title: "报告中心" },
  ];
  await page.goto("/dashboard");
  for (const entry of entries) {
    await page.locator(".sidebar").getByText(entry.menu, { exact: true }).click();
    await expect(page).toHaveURL(entry.url);
    if (entry.menu === "3D全景") {
      await expect(page.locator('[data-testid="panorama-screen"]')).toBeVisible();
      await page.getByRole("button", { name: "← 返回业务平台" }).click();
      await expect(page).toHaveURL(/\/dashboard$/);
    } else {
      await expect(page.locator(".topbar")).toContainText(entry.title);
      await expect(page.locator(".work-tabs")).toContainText(entry.title);
    }
  }
  await expect(page.locator(".sidebar .el-menu-item")).toHaveCount(8);
});

test("3D全景以独立全屏可视化模式打开", async ({ page }) => {
  await page.setViewportSize({width:1920,height:1080});
  const site={id:1,enterprise_id:1,code:"PARK-01",name:"智慧低碳园区",site_type:"PARK",timezone:"Asia/Shanghai",status:"ACTIVE",metadata_json:{},created_at:"2026-01-01",updated_at:"2026-01-01",position_json:{x:0,y:0,z:0}};
    const building={id:1,site_id:1,code:"HBUE-B001",name:"综合办公楼",building_type:"OFFICE",floor_count:8,status:"ACTIVE",metadata_json:{building_id:"HBUE-B001",annual_energy_kwh:120000,annual_water_m3:3200,annual_emission_tco2e:800,data_notice:"示范仿真数据"},position_json:{x:0,y:0,z:0}};
  const device={id:1,enterprise_id:1,external_id:"PV-01",name:"屋顶光伏阵列",device_type:"PV",status:"ACTIVE",metadata_json:{},position_json:{x:12,y:0,z:8}};
  await page.route("**/api/**", async r=>{const p=new URL(r.request().url()).pathname;if(!p.startsWith('/api/'))return r.continue();if(p==="/api/sites")return r.fulfill({json:[site]});if(p==="/api/sites/1/overview")return r.fulfill({json:{site,building_count:1,device_count:1,data_source_count:1,energy_system_count:1,metering_point_count:2,latest_energy:null,latest_carbon_emission_t:8.2,data_completeness_rate:98.5,anomaly_count:1,latest_data_time:"2026-08-27",data_status:"OK"}});if(p==="/api/sites/1/buildings")return r.fulfill({json:[building]});if(p==="/api/sites/1/devices")return r.fulfill({json:[device]});if(p==="/api/sites/1/carbon")return r.fulfill({json:{data_status:"OK",total_emission_t:2860,scope:{},energy:{},factor_sources:[],trend:[{timestamp:"2026-08",emission_t:220}]}});if(p==="/api/buildings/1/carbon")return r.fulfill({json:{data_status:"OK",total_emission_t:800,scope:{},energy:{},factor_sources:[],trend:[]}});if(p==="/api/simulation/batches")return r.fulfill({json:[]});if(p==="/api/devices/1/telemetry")return r.fulfill({json:{object_id:"1",object_type:"DEVICE",metric:"功率",timezone:"Asia/Shanghai",data_status:"OK",data:[{timestamp:"2026-08-27T10:00:00",value:72,unit:"kW"}]}});return r.fulfill({json:[]});});
  await page.goto("/3d");
  await expect(page.locator('[data-testid="panorama-screen"]')).toBeVisible();
  await expect(page.locator('.sidebar')).toHaveCount(0);
  await expect(page.getByText("园区碳能三维全景")).toBeVisible();
  await expect(page.getByRole("button", { name: "← 返回业务平台" })).toBeVisible();
    await expect(page.getByRole("heading",{name:"湖北经济学院 GIS 热力图",exact:true})).toBeVisible();
    await expect(page.getByTestId("gis-layer-control")).toContainText("校园边界");
    await expect(page.getByTestId("gis-layer-control")).toContainText("建筑轮廓");
    await expect(page.getByTestId("gis-layer-control")).toContainText("高能耗热点");
    await expect(page.getByTestId("gis-layer-control")).toContainText("高碳排热点");
    await expect(page.getByTestId("gis-layer-control")).toContainText("跨镜轨迹");
    await expect(page.getByText("示范布点和示范活动路径；实时数据需后端鉴权",{exact:true})).toBeVisible();
    await expect(page.getByText("校园边界与125栋建筑轮廓保持不变",{exact:false})).toBeVisible();
    await expect(page.getByText("建筑碳排排名")).toBeVisible();
    await page.locator('.hotspot.carbon').first().click({force:true});
    await expect(page.locator('.object-drawer')).toContainText('年用电：120,000 千瓦时');
    await expect(page.locator('.object-drawer')).toContainText('年碳排：800 吨二氧化碳当量');
    await page.locator('.drawer-close').click();
  await page.screenshot({path:"../qa_report/3d-panorama.png"});
  await page.getByRole("button",{name:"三维园区",exact:true}).click();
  await expect(page.getByRole("heading",{name:"智慧低碳园区",exact:true})).toBeVisible();
  await page.getByRole("button",{name:"屋顶光伏阵列 光伏"}).click();
  await expect(page.getByText("对象详情")).toBeVisible();
  await expect(page.getByRole("heading",{name:"屋顶光伏阵列",exact:true})).toBeVisible();
});

test("数据接入四步流程与园区对象管理解耦", async ({ page }) => {
  const site = {id:1,enterprise_id:1,organization_node_id:null,code:"E2E-SITE",name:"E2E 园区",site_type:"PARK",address:null,area_m2:null,population:null,timezone:"Asia/Shanghai",status:"ACTIVE",metadata_json:{},longitude:null,latitude:null,position_json:null,geometry_json:null,created_at:"2026-01-01T00:00:00Z",updated_at:"2026-01-01T00:00:00Z"};
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    if (url.pathname === "/api/enterprises") return route.fulfill({json:[{id:1,name:"E2E 企业",base_year:2024}]});
    if (url.pathname === "/api/sites") return route.fulfill({json:[site]});
    if (url.pathname === "/api/sites/1/overview") return route.fulfill({json:{site,building_count:0,device_count:0,data_source_count:0,energy_system_count:0,metering_point_count:0,latest_energy:null,latest_carbon_emission_t:null,data_completeness_rate:null,anomaly_count:0,latest_data_time:null,data_status:"NO_DATA"}});
    if (url.pathname === "/api/data-sources/acquisition-overview") return route.fulfill({json:{source_count:0,normal_source_count:0,abnormal_source_count:0,never_run_count:0,by_type:{},received_last_24h:null,last_success_sync_at:null,last_failure_at:null,validation:{L1_SCHEMA:{rejected:0,passed:null},L2_SEMANTIC:{rejected:0,passed:null},L3_TEMPORAL:{rejected:0,warnings:0,passed:null}},quarantined:0,quality_rate:null,latest_data_at:null,automatic_acquisition_running:false}});
    return route.fulfill({json:[]});
  });
  await page.goto("/data");
  const flow = page.getByRole("navigation", {name:"数据接入流程"});
  await flow.getByRole("button", {name:/1\s*接入对象/}).click();
  await expect(page.getByRole("heading",{name:"选择接入对象"})).toBeVisible();
  await expect(page.getByText("新增建筑")).toHaveCount(0);
  await flow.getByRole("button", {name:/2\s*数据源/}).click();
  await page.getByRole("button", {name:"新增数据源"}).first().click();
  await expect(page.getByRole("dialog", {name:"新增数据源"})).toBeVisible();
  await page.getByRole("dialog").getByRole("button", {name:"Close"}).click();
  await flow.getByRole("button", {name:/3\s*数据采集与导入/}).click();
  await expect(page.getByRole("heading", {name:"数据采集与导入", exact:true})).toBeVisible();
  await expect(page.getByRole("button", {name:"预览并校验"})).toBeVisible();
  await flow.getByRole("button", {name:/4\s*数据质量结果/}).click();
  await expect(page.getByRole("heading",{name:"数据质量结果"})).toBeVisible();
});

test("P3-4 REST 自动采集运行状态和启停可操作", async ({ page }) => {
  const source={id:8,enterprise_id:1,name:"楼控 REST 接口",source_type:"REST_API",config_json:{url:"https://example.invalid/api",field_mapping:{timestamp:"time",value:"reading"}},status:"ACTIVE",has_credentials:true,collection_mode:"INTERVAL",schedule_enabled:false,interval_minutes:60,last_sync_at:"2026-08-25T06:00:00Z"};
  const validation={data_source_id:8,total_records:11,valid_records:10,quarantined_records:1,warning_records:0,quality_rate:10/11,by_stage:{L1_SCHEMA:1}};
  const log={id:1,data_source_id:8,device_external_id:"hvac-01",timestamp:null,level:"ERROR",validation_stage:"L1_SCHEMA",code:"MISSING_FIELDS",message:"missing fields: unit",raw_json:{value:12},created_at:"2026-08-25T06:00:01Z",disposition:"隔离"};
  const detail={source,protocol:"HTTPS",capability:{source_type:"REST_API",acquisition_mode:"定时 API 同步",connection_test:true,manual_sync:true,scheduled_sync:true,realtime_listener:false,automatic_reconnect:false,field_mapping:true,validation_pipeline:["L1_SCHEMA","L2_SEMANTIC","L3_TEMPORAL"],runtime_status:"AVAILABLE",limitation:null},security:{transport:"HTTPS",secure_transport_enabled:true,tls_verification:true,authentication:"凭证/请求头",credentials_configured:true,ca_configured:null,client_certificate_configured:null},binding:{device_count:1,metering_point_count:0,devices:[{id:2,external_id:"hvac-01",name:"一号空调",device_type:"HVAC",status:"ACTIVE"}],metering_points:[]},status:{last_received_at:"2026-08-25T05:59:00Z",received_last_24h:10,cumulative_accepted:10,last_error:log},mapping:{timestamp:"time",value:"reading"},validation,validation_logs:[log]};let running=false;const runtime=()=>({data_source_id:8,source_type:"REST_API",collection_mode:"INTERVAL",schedule_enabled:running,interval_minutes:60,runtime_status:running?"RUNNING":"STOPPED",connected:false,subscribed:false,last_started_at:null,last_success_at:running?"2026-08-25T06:00:00Z":null,last_failure_at:null,next_run_at:running?"2026-08-25T07:00:00Z":null,last_connected_at:null,last_disconnected_at:null,last_message_at:null,last_received_count:11,last_persisted_count:10,last_rejected_count:1,received_count:11,persisted_count:10,rejected_count:1,dropped_count:0,reconnect_count:0,consecutive_failures:0,current_topic:null,last_error:null,incremental_mode:"TIME_WINDOW",current_window_start:"2026-08-25T05:50:00Z",current_window_end:"2026-08-25T06:00:00Z",last_success_watermark:"2026-08-25T06:00:00Z",requested_pages:2,successful_pages:2,failed_page:null,pages_fetched:2,records_fetched:11,duplicates_skipped:3});
  await page.route("**/api/**",async route=>{const p=new URL(route.request().url()).pathname;if(!p.startsWith('/api/'))return route.continue();if(p==="/api/sites")return route.fulfill({json:[{id:1,enterprise_id:1,name:"园区",code:"P1",site_type:"PARK",timezone:"Asia/Shanghai",status:"ACTIVE"}]});if(p==="/api/data-sources")return route.fulfill({json:[source]});if(p==="/api/data-sources/8/details")return route.fulfill({json:detail});if(p==="/api/data-sources/8/runtime")return route.fulfill({json:runtime()});if(p.endsWith('/acquisition-config')){running=true;return route.fulfill({json:runtime()})}if(p.endsWith('/stop')){running=false;return route.fulfill({json:runtime()})}if(p.endsWith('/sync-now'))return route.fulfill({json:{extracted:11,inserted:10,quarantined:1,warnings:0}});if(p.endsWith('/test'))return route.fulfill({json:{success:true,message:"connected"}});return route.fulfill({json:[]})});
  await page.goto("/system/data-sources");
  await page.getByRole("button",{name:"查看详情"}).click();
  await page.getByRole('button',{name:'启动自动采集'}).click();
  await expect(page.getByRole("dialog")).toContainText("RUNNING");
  await expect(page.getByRole("dialog")).toContainText("下次运行");
  await expect(page.getByRole("dialog")).toContainText("成功业务水位");
  await expect(page.getByRole("dialog")).toContainText("2 页 / 11 条");
  await expect(page.getByRole("dialog")).toContainText("幂等跳过");
  await page.getByRole('button',{name:'立即同步'}).click();
  await page.getByRole("tab",{name:"安全传输"}).click();
  await expect(page.getByRole("dialog")).toContainText("已配置（已脱敏）");
  await page.getByRole("tab",{name:"字段映射"}).click();
  await expect(page.getByRole("dialog")).toContainText("reading");
  await page.getByRole("tab",{name:"三级校验与隔离"}).click();
  await expect(page.getByRole("dialog")).toContainText("L1_SCHEMA");
  await expect(page.getByRole("dialog")).toContainText("missing fields: unit");
  await page.getByRole('button',{name:'停止自动采集'}).click();
  await expect(page.getByRole("dialog")).toContainText("STOPPED");
});

test("园区管理内创建园区并继续配置建筑", async ({ page }) => {
  const created = {id:901,enterprise_id:1,organization_node_id:null,code:"PW-SITE",name:"自动化园区",site_type:"PARK",address:"测试地址",area_m2:null,population:null,timezone:"Asia/Shanghai",status:"ACTIVE",metadata_json:{},longitude:null,latitude:null,position_json:null,geometry_json:null,created_at:"2026-01-01T00:00:00Z",updated_at:"2026-01-01T00:00:00Z"};
  let createdDone=false;await page.route("**/api/**", async route => {const path=new URL(route.request().url()).pathname;if(!path.startsWith("/api/"))return route.continue();if(path==="/api/enterprises")return route.fulfill({json:[{id:1,name:"测试企业",base_year:2024}]});if(path==="/api/sites"&&route.request().method()==="POST"){createdDone=true;return route.fulfill({json:created})}if(path==="/api/sites")return route.fulfill({json:createdDone?[created]:[]});return route.fulfill({json:[]});});
  await page.goto("/park?create=site");
  await page.locator('.el-form-item').filter({hasText:'所属企业或组织'}).locator('.el-select').click();await page.getByRole('option',{name:'测试企业'}).click();
  await page.getByLabel("园区名称").fill("自动化园区");await page.getByLabel("园区编码").fill("PW-SITE");
  await page.getByRole("button",{name:"创建园区"}).click();
  await page.getByRole('tab',{name:'建筑'}).click();await page.getByRole('button',{name:'新增建筑'}).click();
  await expect(page.getByRole('dialog',{name:'新增建筑'})).toBeVisible();
});

test("仿真工作台只展开当前措施且集成后续业务入口", async ({ page }) => {
  const site={id:1,enterprise_id:1,code:"S",name:"仿真园区",site_type:"PARK",timezone:"Asia/Shanghai",status:"ACTIVE",metadata_json:{},created_at:"2026-01-01",updated_at:"2026-01-01"};
  await page.route("**/api/**",async route=>{const path=new URL(route.request().url()).pathname;if(!path.startsWith("/api/"))return route.continue();if(path==="/api/sites")return route.fulfill({json:[site]});if(path.includes("/models"))return route.fulfill({json:{models:[],measure_types:[]}});return route.fulfill({json:[]});});
  await page.goto("/simulation");
  await expect(page.getByRole("heading",{name:"碳中和仿真工作台"})).toBeVisible();
  await page.getByRole("button",{name:/风电（WIND）/}).click();
  await expect(page.getByText("风电（WIND）参数",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"恢复默认"}).click();
  await expect(page.getByRole("button",{name:"智能推荐"})).toBeVisible();
  await expect(page.getByRole("button",{name:"场景比较"})).toBeVisible();
  await expect(page.getByRole("button",{name:"生成报告"})).toBeDisabled();
});
