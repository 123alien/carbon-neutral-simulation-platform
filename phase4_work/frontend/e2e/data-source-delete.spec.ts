import {expect,test} from '@playwright/test'

test('data source management exposes guarded delete action',async({page})=>{
  await page.goto('/system/data-sources')
  await expect(page.getByTestId('system-data-sources-page')).toBeVisible({timeout:15_000})
  await expect(page.getByText('平台范围 · 全部园区')).toBeVisible()
  await expect(page.getByText('BDG2 Rat 2016 observed electricity')).toBeVisible()
  await expect(page.getByText('ACN-Data static session energy')).toBeVisible()
  await expect(page.getByRole('button',{name:'删除'}).first()).toBeVisible()
})
