import {expect,test} from '@playwright/test'

// BDG2 公开验证资产已按当前 Demo 收口要求删除。本用例仅保留为历史验收说明，
// 不再作为正式 Demo 核心业务回归，也不通过恢复数据来制造通过结果。
test.skip('P4 immutable real baseline exposes provenance and verified metrics',async({page})=>{
  await page.goto('/scenarios?scenario=1')
  const baseline=page.getByTestId('experiment-baseline')
  await expect(baseline).toBeVisible({timeout:15_000})
  await expect(baseline).toContainText('实验基准')
  await expect(baseline).toContainText('BDG2_V1_RAT_2016')
  await expect(baseline).toContainText('25,543,735.06 kWh')
  await expect(baseline).toContainText('11,567.905015 tCO₂e')
  await expect(baseline).toContainText('FUNCTION_PARAMETER_ONLY')
  await expect(baseline).not.toContainText('NaN')
})
