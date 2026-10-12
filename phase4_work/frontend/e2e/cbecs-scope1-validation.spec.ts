import {expect,test} from '@playwright/test'

const api='http://127.0.0.1:8000'

test('CBECS official annual multi-energy accounting is traceable at Site and Building levels',async({page})=>{
  const sitesResponse=await page.request.get(`${api}/api/sites`)
  expect(sitesResponse.ok()).toBeTruthy()
  const site=(await sitesResponse.json()).find((item:{code:string})=>item.code==='CBECS-SCOPE1')
  expect(site).toBeTruthy()

  const buildingsResponse=await page.request.get(`${api}/api/sites/${site.id}/buildings`)
  expect(buildingsResponse.ok()).toBeTruthy()
  const buildings=await buildingsResponse.json()
  expect(buildings).toHaveLength(3)

  const carbonResponse=await page.request.get(`${api}/api/sites/${site.id}/carbon?start_time=2018-01-01T00:00:00Z&end_time=2019-01-01T00:00:00Z&granularity=year`)
  expect(carbonResponse.ok()).toBeTruthy()
  const carbon=await carbonResponse.json()
  expect(carbon.data_status).toBe('OK')
  expect(carbon.scope.SCOPE_1).toBeCloseTo(318.102105,5)
  expect(carbon.scope.SCOPE_2).toBeCloseTo(20533.332961,5)
  expect(carbon.energy.natural_gas).toBeGreaterThan(0)
  expect(carbon.energy.oil).toBeGreaterThan(0)
  expect(carbon.energy.heat).toBeGreaterThan(0)

  const enterprises=await (await page.request.get(`${api}/api/enterprises`)).json()
  const enterprise=enterprises.find((item:{name:string})=>item.name==='EIA CBECS 2018 Scope 1 Validation')
  const runs=await (await page.request.get(`${api}/api/carbon-accounting/runs?enterprise_id=${enterprise.id}`)).json()
  const run=runs.find((item:{name:string})=>item.name.includes('CBECS 2018 official'))
  const results=await (await page.request.get(`${api}/api/carbon-accounting/runs/${run.id}/results`)).json()
  expect(results).toHaveLength(12)
  expect(results.every((item:{activity_source:string;factor_source:string})=>item.activity_source.includes('REAL_PUBLIC_OFFICIAL')&&item.factor_source.includes('US EPA'))).toBeTruthy()

  await page.goto(`/carbon?site=${site.id}`)
  await expect(page.locator('#app')).not.toBeEmpty()
  await expect(page.locator('body')).not.toContainText('NaN')
})
