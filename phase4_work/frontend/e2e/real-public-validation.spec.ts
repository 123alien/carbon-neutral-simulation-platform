import {test,expect} from '@playwright/test'

test('P3-5 公开真实数据在核心页面可读取且不出现 NaN',async({page})=>{
  const routes=['/dashboard','/data','/carbon','/simulation?scenario_version=1','/scenarios?scenario=1','/recommendations?site=1','/risks?scenario_version=1&task=1','/reports?scenario_version=1&task=1','/screen','/3d']
  for(const route of routes){
    await page.goto(route)
    await expect(page.locator('#app')).not.toBeEmpty()
    await expect(page.locator('body')).not.toContainText('NaN')
  }
})

test('P3-5 正式报告显示冻结快照并可追溯公开数据',async({page})=>{
  await page.goto('/reports?scenario_version=1&task=1')
  await expect(page.locator('#app')).not.toBeEmpty()
  await expect(page.locator('body')).not.toContainText('NaN')
  const response=await page.request.get('http://127.0.0.1:8000/api/reports/feasibility/2')
  expect(response.ok()).toBeTruthy()
  const report=await response.json()
  expect(report.status).toBe('SUCCESS')
  expect(report.report_data_json.data_provenance.classification).toBe('公开真实数据')
  expect(report.report_data_json.data_provenance.sites[0].dataset_id).toBe('BDG2_V1_RAT_2016')
  expect(report.files.map((item:{format:string})=>item.format).sort()).toEqual(['DOCX','PDF'])
})
