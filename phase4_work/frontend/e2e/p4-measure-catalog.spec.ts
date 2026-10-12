import {expect,test} from '@playwright/test'

test('P4 audited measure library exposes source status and three scales',async({page})=>{
  const response=await page.request.get('http://127.0.0.1:8000/api/recommendations/measure-catalog')
  expect(response.ok()).toBeTruthy()
  const catalog=await response.json()
  expect(catalog.measures).toHaveLength(7)
  expect(catalog.measures.find((x:{measure_code:string})=>x.measure_code==='LIGHTING').recommendation_status).toBe('BLOCKED_BY_ACCESS')
  await page.goto('/recommendations?site=1')
  const library=page.getByTestId('audited-measure-library')
  await expect(library).toBeVisible({timeout:15_000})
  await expect(library).toContainText('P4-2-v1')
  await expect(library).toContainText('CALIBRATED')
  await expect(library).toContainText('BLOCKED_BY_ACCESS')
  await expect(library).not.toContainText('NaN')
})
