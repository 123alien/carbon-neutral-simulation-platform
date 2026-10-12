import {test,expect} from '@playwright/test'

test('P3-5.2 ACN EV 真实数据对象和会话电量可读取',async({page})=>{
  const site=await page.request.get('http://127.0.0.1:8000/api/sites/2')
  expect(site.ok()).toBeTruthy()
  expect((await site.json()).metadata_json.dataset_id).toBe('ACN_DATA_STATIC_CALTECH_2018_05')
  const devices=await page.request.get('http://127.0.0.1:8000/api/sites/2/devices')
  const rows=await devices.json()
  expect(rows).toHaveLength(3)
  expect(rows.every((item:{device_type:string})=>item.device_type==='EV_CHARGER')).toBeTruthy()
  const telemetry=await page.request.get('http://127.0.0.1:8000/api/devices/6/telemetry?start_time=2018-05-01T00%3A00%3A00Z&end_time=2018-05-16T00%3A00%3A00Z&metric_name=energy_kwh&granularity=day&timezone=America%2FLos_Angeles')
  const data=await telemetry.json()
  expect(data.data_status).toBe('OK')
  expect(data.data[0].timestamp).toContain('-07:00')
  expect(data.data.every((item:{unit:string,value:number})=>item.unit==='kWh'&&Number.isFinite(item.value))).toBeTruthy()
  await page.goto('/data')
  await expect(page.locator('#app')).not.toBeEmpty()
  await expect(page.locator('body')).not.toContainText('NaN')
})
