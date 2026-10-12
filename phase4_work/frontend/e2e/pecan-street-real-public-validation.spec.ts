import {test,expect} from '@playwright/test'
test('P3-5.5 Pecan Street HVAC 实测数据可读取且无伪造设备',async({page})=>{
 const sites=await page.request.get('http://127.0.0.1:8000/api/sites');const site=(await sites.json()).find((x:{code:string})=>x.code==='PECAN-PUBLIC');expect(site.metadata_json.data_class).toBe('REAL_PUBLIC');expect(site.metadata_json.storage).toBe('BLOCKED_BY_ACCESS')
 const dr=await page.request.get(`http://127.0.0.1:8000/api/sites/${site.id}/devices`);const devices=await dr.json();expect(devices).toHaveLength(3);expect(devices.every((x:{device_type:string})=>x.device_type==='HVAC')).toBeTruthy()
 const tr=await page.request.get(`http://127.0.0.1:8000/api/devices/${devices[0].id}/telemetry?start_time=2018-08-23T00%3A00%3A00Z&end_time=2018-08-26T00%3A01%3A00Z&metric_name=hvac_power_kw&granularity=hour&timezone=UTC`);const telemetry=await tr.json();expect(telemetry.data_status).toBe('OK');expect(telemetry.data.every((x:{value:number})=>Number.isFinite(x.value))).toBeTruthy()
 const sources=await page.request.get('http://127.0.0.1:8000/api/data-sources');const source=(await sources.json()).find((x:{name:string})=>x.name==='Pecan Street official public sample FILE');const qr=await page.request.get(`http://127.0.0.1:8000/api/data-sources/${source.id}/data-quality`);expect((await qr.json()).valid_records).toBe(38889)
 await page.goto('/data');await expect(page.locator('#app')).not.toBeEmpty();await expect(page.locator('body')).not.toContainText('NaN')
})
