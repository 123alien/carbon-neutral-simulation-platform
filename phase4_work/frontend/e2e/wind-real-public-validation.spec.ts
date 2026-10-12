import {test,expect} from '@playwright/test'

test('P3-5.3 Kelmarsh WIND 真实数据可读取且页面无 NaN',async({page})=>{
  const sites=await page.request.get('http://127.0.0.1:8000/api/sites')
  const site=(await sites.json()).find((item:{code:string})=>item.code==='KELMARSH-WIND')
  expect(site.metadata_json.data_class).toBe('REAL_PUBLIC')
  const devices=await page.request.get(`http://127.0.0.1:8000/api/sites/${site.id}/devices`)
  const rows=await devices.json()
  expect(rows).toHaveLength(3)
  expect(rows.every((item:{device_type:string})=>item.device_type==='WIND')).toBeTruthy()
  for(const metric of ['wind_speed_m_s','active_power_kw']){
    const response=await page.request.get(`http://127.0.0.1:8000/api/devices/${rows[0].id}/telemetry?start_time=2016-12-18T00%3A00%3A00Z&end_time=2017-01-01T00%3A00%3A00Z&metric_name=${metric}&granularity=hour&timezone=UTC`)
    const body=await response.json()
    expect(body.data_status).toBe('OK')
    expect(body.data.length).toBeGreaterThan(0)
    expect(body.data.every((item:{value:number})=>Number.isFinite(item.value))).toBeTruthy()
  }
  await page.goto('/data')
  await expect(page.locator('#app')).not.toBeEmpty()
  await expect(page.locator('body')).not.toContainText('NaN')
})
