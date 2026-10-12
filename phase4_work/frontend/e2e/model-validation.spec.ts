import {expect,test} from '@playwright/test'
const api='http://127.0.0.1:8000'
test('Wind/PV实测与仿真留出集、参数来源和报告快照可追溯',async({page})=>{
 const wind=await (await page.request.get(`${api}/api/model-validation/WIND`)).json()
 const pv=await (await page.request.get(`${api}/api/model-validation/PV`)).json()
 for(const item of [wind,pv]){
  expect(item.metrics.after.rmse_kw).toBeLessThan(item.metrics.before.rmse_kw)
  expect(item.series.length).toBeGreaterThan(100)
  expect(item.fallback_code).toBe('MODEL_PARAMETER_FALLBACK')
 }
 await page.goto('/model-validation')
 await expect(page.getByRole('heading',{name:'实测与仿真对比'})).toBeVisible()
 await expect(page.getByText('MODEL_PARAMETER_FALLBACK').first()).toBeVisible()
 await expect(page.getByText('Observed vs Simulated 功率曲线')).toBeVisible()
 await page.getByRole('tab',{name:'光伏（PV）'}).click()
 await expect(page.getByText('SolarIrradianceModel/V2')).toBeVisible()
 await expect(page.locator('body')).not.toContainText('NaN')

 const reference=await (await page.request.get(`${api}/api/reports/feasibility/2`)).json()
 const all=await (await page.request.get(`${api}/api/reports?scenario_version_id=${reference.scenario_version_id}`)).json()
 let report=all.find((x:{title:string})=>x.title==='P3-6 模型验证摘要报告')
 if(!report){report=await (await page.request.post(`${api}/api/reports/feasibility`,{data:{enterprise_id:reference.enterprise_id,scenario_version_id:reference.scenario_version_id,simulation_task_id:reference.simulation_task_id,title:'P3-6 模型验证摘要报告'}})).json()}
 expect(report.report_data_json.model_validation.map((x:{model:string})=>x.model).sort()).toEqual(['PV','WIND'])
 expect(report.report_data_json.model_validation.every((x:{fallback_code:string})=>x.fallback_code==='MODEL_PARAMETER_FALLBACK')).toBeTruthy()
})
