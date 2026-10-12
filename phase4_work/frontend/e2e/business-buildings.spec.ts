import {test,expect} from '@playwright/test';
import * as THREE from 'three';
import {businessBuilding} from '../src/utils/businessBuildings';

for(const [type,floors] of [['OFFICE',12],['LAB',8],['SERVICE',6]] as const){
  test(`${type} 建筑外形保留边界、楼层数和设备屋顶支撑面`,()=>{
    const height=floors*2.8,roof=height-.35;
    const group=businessBuilding(type,floors,height,roof);
    const bounds=new THREE.Box3().setFromObject(group);
    expect(bounds.min.y).toBeCloseTo(0);expect(bounds.max.y).toBeCloseTo(height);
    expect(bounds.max.x-bounds.min.x).toBeLessThanOrEqual(22.2);
    expect(bounds.max.z-bounds.min.z).toBeLessThanOrEqual(17.2);
    expect(group.userData.floorCount).toBe(floors);
    const ray=new THREE.Raycaster(new THREE.Vector3(0,height+5,0),new THREE.Vector3(0,-1,0));
    expect(ray.intersectObject(group,true)[0].point.y).toBeCloseTo(roof);
    expect(group.userData.architecture).toBe(type==='SERVICE'?'SERVICE_TERRACE':type==='OFFICE'?'OFFICE_GRID':'LAB_WINGS');
    // Geometry is batched: detailed windows do not create hundreds of draw calls.
    expect(group.children.length).toBeLessThanOrEqual(5);
  });
}
test('实验楼门厅凹入两翼，办公楼保持完整办公体量',()=>{
  const lab=businessBuilding('LAB',8,22.4),office=businessBuilding('OFFICE',12,33.6);
  const ray=new THREE.Raycaster(new THREE.Vector3(0,30,7),new THREE.Vector3(0,-1,0));
  expect(ray.intersectObject(lab,true)).toHaveLength(0);
  ray.ray.origin.y=40;
  expect(ray.intersectObject(office,true).length).toBeGreaterThan(0);
});
