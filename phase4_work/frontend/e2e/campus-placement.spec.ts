import {test,expect} from '@playwright/test';
import * as THREE from 'three';
import {normalizeAsset} from '../src/utils/campusGeometry';
import {validateSpatial} from '../src/utils/spatial';
import type {Building,Site} from '../src/types';

test('模型原点偏移及小单位尺寸正确归一化，单材质不变成数组',()=>{
  const geometry=new THREE.BoxGeometry(.4,.8,.3);geometry.translate(2,4,-3);
  const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial());
  const root=normalizeAsset(mesh,new THREE.Vector3(22,32,17));
  const bounds=new THREE.Box3().setFromObject(root),size=bounds.getSize(new THREE.Vector3());
  expect(bounds.min.y).toBeCloseTo(0);expect(bounds.getCenter(new THREE.Vector3()).x).toBeCloseTo(0);
  expect(size.x).toBeCloseTo(22);expect(size.y).toBeCloseTo(32);expect(size.z).toBeCloseTo(17);
  expect(Array.isArray(mesh.material)).toBe(false);
});
test('三维局部坐标保留Y高程，不将Z平面坐标变为高度',()=>{
  const site={id:7,longitude:114.31,latitude:30.52} as Site;
  const building={id:9,name:'办公楼A',building_type:'OFFICE',position_json:{x:-38,y:0,z:-22}} as Building;
  const result=validateSpatial([building],site,'BUILDING');
  expect(result.objects[0].coordinate).toMatchObject({x:-38,y:0,z:-22});
});
test('实际园区画面、模型资源及建筑点击（只读）',async({page})=>{
  test.skip(!process.env.VERIFY_LIVE_CAMPUS,'显式启用：使用现有后端，只读，不灌入测试数据');
  test.setTimeout(90000);
  const errors:string[]=[];const modelFailures:string[]=[];const palettes=new Set<string>();
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.url().includes('/models/')){if(r.status()>=400)modelFailures.push(r.url());if(r.url().endsWith('colormap.png')&&r.ok())palettes.add(r.url());}});
  await page.setViewportSize({width:1920,height:1080});
  await page.goto('/3d?site=7');
  await expect(page.locator('.campus-label')).toHaveCount(4,{timeout:60000});
  await expect.poll(()=>palettes.size).toBe(2);
  await expect(page.locator('.three-shell')).toHaveAttribute('data-models-ready','true');
  await expect(page.locator('.three-canvas canvas')).toBeVisible();
  await page.screenshot({path:'artifacts/campus-live-overview.png',fullPage:true});
  await page.locator('.campus-label').filter({hasText:'办公楼A'}).click({timeout:10000});
  await expect(page.locator('.object-drawer')).toContainText('办公楼A');
  await expect(page.locator('.campus-label')).toHaveCount(4);
  await expect(page.locator('.three-shell')).toHaveAttribute('data-models-ready','true');
  await page.screenshot({path:'artifacts/campus-live-building.png',fullPage:true});
  expect(modelFailures).toEqual([]);expect(errors).toEqual([]);
});
