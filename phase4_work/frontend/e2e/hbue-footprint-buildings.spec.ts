import {test,expect} from '@playwright/test';
test('三栋校园建筑真实底面和近景查看',async({page})=>{
 const site={id:15,enterprise_id:15,code:'HBUE',name:'湖北经济学院智慧低碳校园',longitude:114.42966,latitude:30.42023,metadata_json:{campus_id:'HBUE'}};
 const buildings=[['HBUE-B120','教学楼一',114.433,30.421],['HBUE-B119','教学楼二',114.434,30.422],['HBUE-B041','实验楼一',114.431,30.419]].map((r,i)=>({id:i+1,site_id:15,code:r[0],name:r[1],longitude:r[2],latitude:r[3],floor_count:5,building_type:i===2?'LAB':'TEACHING',metadata_json:{building_id:r[0]}}));
 await page.setViewportSize({width:1920,height:1080});
 await page.route('**/api/**',route=>{
  const path=new URL(route.request().url()).pathname;if(!path.startsWith('/api/'))return route.continue();
  if(path==='/api/sites')return route.fulfill({json:[site]});
  if(path.endsWith('/buildings'))return route.fulfill({json:buildings});
  if(path.endsWith('/overview'))return route.fulfill({json:{site,anomaly_count:0}});
  if(path.endsWith('/carbon'))return route.fulfill({json:{total_emission_t:null,trend:[]}});
  return route.fulfill({json:[]});
 });
 await page.goto('/3d');await page.getByRole('button',{name:'三维园区',exact:true}).click();
 await expect(page.locator('.campus-model-notice')).toBeVisible();
 await expect(page.locator('.three-canvas canvas')).toBeVisible();
 await page.getByRole('button',{name:'校园总览',exact:true}).click();
 await expect(page.locator('.campus-label')).toHaveCount(3);
 await page.screenshot({path:'../qa_report/hbue-campus-display-clean.png'});
 await page.getByRole('button',{name:'重点建筑区',exact:true}).click();
 await expect(page.locator('.campus-focus')).not.toContainText('查看教学楼');
 await page.locator('.campus-label').filter({hasText:'教学楼一'}).click();
 await page.screenshot({path:'../qa_report/hbue-teaching-footprint.png'});
 await page.getByRole('button',{name:'校园总览',exact:true}).click();
 await page.locator('.campus-label').filter({hasText:'实验楼一'}).click();
 await page.screenshot({path:'../qa_report/hbue-laboratory-footprint.png'});
 // Let orbit damping settle: an idle view must stop rendering WebGL frames.
 await page.waitForTimeout(1500);
 const canvasHost=page.locator('.three-canvas');
 const settled=await canvasHost.getAttribute('data-render-count');
 expect(Number(settled)).toBeGreaterThan(0);
 await page.waitForTimeout(500);
 expect(await canvasHost.getAttribute('data-render-count')).toBe(settled);
 expect(Number(await canvasHost.getAttribute('data-draw-calls'))).toBeLessThan(180);
 await page.getByRole('button',{name:'校园总览',exact:true}).click();
 await expect.poll(async()=>Number(await canvasHost.getAttribute('data-render-count'))).toBeGreaterThan(Number(settled));
});
