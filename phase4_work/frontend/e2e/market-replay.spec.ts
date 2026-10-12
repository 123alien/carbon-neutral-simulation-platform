import {test,expect} from '@playwright/test';

test('实际示范行情回放、深色文字、暂停及冻结评估隔离',async({page})=>{
  test.setTimeout(60000);
  const writes:string[]=[];page.on('request',r=>{if(r.url().includes('/api/')&&r.method()!=='GET')writes.push(r.url());});
  await page.setViewportSize({width:1440,height:1000});
  await page.goto('/carbon-market');
  const replay=page.getByTestId('market-replay'),frozen=page.getByTestId('frozen-market-parameters');
  await expect(replay).toContainText('示范行情回放',{timeout:30000});
  await expect(replay).toContainText('非实时行情');
  await expect(frozen).toBeVisible();
  await expect(frozen.locator('b').first()).toHaveCSS('color','rgb(23, 62, 55)');
  const snapshot=await frozen.innerText(),cost=await page.locator('.market-cards').innerText();
  const count=await page.getByLabel('回放统计期',{exact:true}).locator('option').count();
  expect(count).toBeGreaterThan(1);
  await page.clock.install();
  await page.getByLabel('回放统计期',{exact:true}).selectOption('0');
  await expect(page.getByTestId('replay-progress')).toContainText(`1 / ${count}`);
  const first=await page.getByTestId('quote-carbon_price_per_t').innerText();
  await page.getByRole('button',{name:'播放回放',exact:true}).click();
  await page.clock.fastForward(1500);
  await expect(page.getByTestId('replay-progress')).toContainText(`2 / ${count}`);
  await expect(page.getByTestId('quote-carbon_price_per_t')).not.toHaveText(first);
  await page.getByRole('button',{name:'暂停回放',exact:true}).click();
  await page.clock.fastForward(5000);
  await expect(page.getByTestId('replay-progress')).toContainText(`2 / ${count}`);
  await page.getByLabel('播放速度',{exact:true}).selectOption('750');
  await page.getByRole('button',{name:'播放回放',exact:true}).click();
  await page.clock.fastForward(750);
  await expect(page.getByTestId('replay-progress')).toContainText(`3 / ${count}`);
  await page.getByRole('button',{name:'查看全部',exact:true}).click();
  await expect(page.getByTestId('replay-progress')).toContainText(`${count} / ${count}`);
  expect(await frozen.innerText()).toBe(snapshot);expect(await page.locator('.market-cards').innerText()).toBe(cost);
  expect(writes).toEqual([]);
  await page.getByTestId('market-statistics').scrollIntoViewIfNeeded();
  await page.screenshot({path:'artifacts/market-replay-live.png',fullPage:false});
});

test('零值、缺失、空记录、查询失败可恢复',async({page})=>{
  let response:'records'|'empty'|'error'='records';
  await page.route('**/api/carbon-market/statistics**',route=>{
    if(response==='error')return route.fulfill({status:503,json:{detail:'市场查询暂时不可用'}});
    return route.fulfill({json:{region:'DEMO_REGION',record_count:response==='empty'?0:1,quality:response==='empty'?'NO_DATA':'COMPLETE',indicators:{},records:response==='empty'?[]:[{id:1,region:'DEMO_REGION',timestamp:'2024-01-01T00:00:00Z',carbon_price_per_t:0,trading_volume_t:null,source:'隔离回放测试记录'}]}});
  });
  await page.goto('/carbon-market');
  await expect(page.getByTestId('quote-carbon_price_per_t')).toContainText('0',{timeout:30000});
  await expect(page.getByTestId('quote-trading_volume_t')).toContainText('暂无数据');
  await expect(page.getByRole('button',{name:'播放回放',exact:true})).toBeDisabled();
  response='error';await page.getByRole('button',{name:'查询',exact:true}).click();
  await expect(page.getByTestId('market-statistics')).toContainText('市场查询暂时不可用');
  response='empty';await page.getByRole('button',{name:'查询',exact:true}).click();
  await expect(page.getByTestId('market-statistics')).toContainText('暂无碳市场数据');
  response='records';await page.getByRole('button',{name:'查询',exact:true}).click();
  await expect(page.getByTestId('quote-carbon_price_per_t')).toContainText('0');
});
