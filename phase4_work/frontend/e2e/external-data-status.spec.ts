import {test,expect} from '@playwright/test';
test('真实数据待绑定区和上游空值如实展示',async({page})=>{
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;
  if(!path.startsWith('/api/'))return route.continue();
  if(path==='/api/external-data/status')return route.fulfill({json:{IOT_CLOUD:{connected:false,credentials_configured:false},WEATHER_STATION:{connected:true,property_count:17,valid_value_count:0,collected_at:'2026-09-16T10:00:00'}}});
  if(path==='/api/external-data/records')return route.fulfill({json:[{id:1,payload:{source_type:'WEATHER_STATION',device_name:'气象站',metric_name:'空气温度',value:null,unit:'℃',timestamp:null,quality_status:'MISSING_VALUE',building_id:null}}]});
  return route.fulfill({json:[]});
 });
 await page.goto('/data');
 const panel=page.getByTestId('external-data-status');
 await expect(panel).toContainText('未配置凭证');
 await expect(panel).toContainText('有效观测 0');
 await panel.locator('select').first().selectOption('WEATHER_STATION');
 await panel.locator('select').nth(1).selectOption('METRIC');
 await panel.getByRole('button',{name:'查看记录'}).click();
 await expect(panel).toContainText('上游未返回观测值');
 await expect(panel).toContainText('空气温度');
 await page.screenshot({path:'../qa_report/external-data-status.png'});
});
