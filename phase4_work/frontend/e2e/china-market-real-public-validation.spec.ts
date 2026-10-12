import {expect,test} from '@playwright/test'
const api='http://127.0.0.1:8000'
test('中国官方全国碳市场、CCER、绿证年度统计可追溯且页面无 NaN',async({page})=>{
 const response=await page.request.get(`${api}/api/carbon-market/statistics?region=${encodeURIComponent('中国全国市场')}`)
 expect(response.ok()).toBeTruthy();const data=await response.json()
 expect(data.record_count).toBe(5)
 expect(data.records.filter((x:{trading_volume_t:number|null})=>x.trading_volume_t!=null)).toHaveLength(2)
 expect(data.indicators.trading_amount_yuan.sum).toBe(32744000000)
 expect(data.indicators.ccer_volume_t.sum).toBe(9219400)
 expect(data.indicators.ccer_trading_amount_yuan.sum).toBe(650000000)
 expect(data.indicators.green_certificate_issued_count.sum).toBe(7681000000)
 expect(data.indicators.green_certificate_traded_count.sum).toBe(1376000000)
 expect(data.records.every((x:{source:string})=>x.source.includes('REAL_PUBLIC_OFFICIAL'))).toBeTruthy()
 await page.goto(`/carbon-market?region=${encodeURIComponent('中国全国市场')}`)
 await expect(page.getByRole('heading',{name:'市场指标趋势'})).toBeVisible()
 await expect(page.getByText('18,114,000,000').first()).toBeVisible()
 await expect(page.locator('body')).not.toContainText('NaN')
})
