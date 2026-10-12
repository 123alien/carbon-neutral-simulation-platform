import {test,expect} from '@playwright/test';
test('大屏组件不裁切，地图控件与底部指标不重叠',async({page,request})=>{
 test.setTimeout(60000);
 const sites=await(await request.get('http://127.0.0.1:8000/api/sites')).json();const site=sites.find((s:{code:string})=>s.code==='HBUE');
 await page.goto(`/3d?site=${site.id}`);await expect(page.getByTestId('campus-live-notice')).toBeVisible();
 for(const [width,height] of [[1920,1080],[1920,945],[1366,768]]){
  await page.setViewportSize({width,height});await page.waitForTimeout(400);
  for(const selector of ['.left-top','.left-bottom','.right-top','.right-middle']){
   const result=await page.locator(selector).evaluate(panel=>{const p=panel.getBoundingClientRect(),chart=panel.querySelector('.chart-wrap')!.getBoundingClientRect();return {contained:chart.bottom<=p.bottom&&chart.top>=p.top,positive:chart.height>35}});
   expect(result).toEqual({contained:true,positive:true});
  }
  const components=await page.evaluate(()=>{
   const rect=(s:string)=>document.querySelector(s)!.getBoundingClientRect();const cap=rect('.scene-caption'),map=rect('.spatial-viewport'),kpi=rect('.scene-kpis'),legend=rect('.gis-legend'),controls=rect('.layer-control');
   return {header:cap.bottom<=map.top+1,footer:map.bottom<=kpi.top+1,legend:legend.bottom<=kpi.top,controls:controls.top>=map.top,inside:rect('.panorama-dashboard').bottom<=window.innerHeight};
  });expect(Object.values(components).every(Boolean)).toBeTruthy();
  await page.screenshot({path:`../qa_report/panorama-layout-${width}-${height}.png`});
 }
 await page.getByTestId('gis-layer-control').getByText('跨镜轨迹',{exact:true}).click();
 await expect(page.getByTestId('trajectory-panel')).toBeVisible();
 const trajectory=await page.getByTestId('trajectory-panel').boundingBox(),kpi=await page.locator('.scene-kpis').boundingBox();expect(trajectory!.y+trajectory!.height).toBeLessThanOrEqual(kpi!.y);
});
