import {test,expect} from '@playwright/test'

test('P3-5.4 PVDAQ 实测 PV 数据可读取且页面无 NaN',async({page})=>{
 const sites=await page.request.get('http://127.0.0.1:8000/api/sites');const site=(await sites.json()).find((x:{code:string})=>x.code==='PVDAQ-35')
 expect(site.metadata_json.data_class).toBe('REAL_PUBLIC')
 const devices=await page.request.get(`http://127.0.0.1:8000/api/sites/${site.id}/devices`);const rows=await devices.json();expect(rows).toHaveLength(1);expect(rows[0].device_type).toBe('PV')
 for(const metric of ['poa_irradiance_w_m2','ambient_temperature_c','ac_power_kw']){
  const r=await page.request.get(`http://127.0.0.1:8000/api/devices/${rows[0].id}/telemetry?start_time=2010-10-01T07%3A00%3A00Z&end_time=2010-10-15T07%3A00%3A00Z&metric_name=${metric}&granularity=hour&timezone=America%2FLos_Angeles`);const body=await r.json()
  expect(body.data_status).toBe('OK');expect(body.data.length).toBeGreaterThan(0);expect(body.data.every((x:{value:number})=>Number.isFinite(x.value))).toBeTruthy()
 }
 const quality=await page.request.get('http://127.0.0.1:8000/api/data-sources/4/data-quality');expect((await quality.json()).valid_records).toBe(6717)
 await page.goto('/data');await expect(page.locator('#app')).not.toBeEmpty();await expect(page.locator('body')).not.toContainText('NaN')
})
