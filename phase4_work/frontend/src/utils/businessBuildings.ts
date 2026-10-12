import * as THREE from 'three';

/** Purpose-specific illustrative architecture, within the existing 22 × 17 envelope.
 * Not a surveyed/BIM model; no business metadata or device coordinates are changed.
 */
export function businessBuilding(type:string,floors:number,height:number,roofHeight=height-.35) {
  const lab=type.toUpperCase().includes('LAB'),service=type.toUpperCase().includes('SERVICE'),group=new THREE.Group();
  group.name=service?'综合服务楼：公共门厅与退台窗带':lab?'实验楼：双翼与中央连接体':'办公楼：规则办公窗格与玻璃门厅';
  const materials=[0xe1e3de,0x375b6b,0x9eacb0,0x55646a,0xd1c4ae].map(color=>new THREE.MeshStandardMaterial({color,roughness:.65,metalness:.08}));
  const batches=materials.map(()=>[] as THREE.Matrix4[]);
  function box(w:number,h:number,d:number,x:number,y:number,z:number,m=0){
    batches[m].push(new THREE.Matrix4().compose(new THREE.Vector3(x,y,z),new THREE.Quaternion(),new THREE.Vector3(w,h,d)));
  }
  const n=Math.max(1,Math.min(40,Math.round(floors))),step=roofHeight/n;
  if(service){
    const podium=Math.min(2,n)*step;
    box(21.6,podium,16.6,0,podium/2,0,4);
    // Public-facing double-height lobby, recessed beneath a broad entrance canopy.
    box(17,podium-.5,.12,0,podium/2,8.34,1);
    for(const x of [-7.5,-5,-2.5,0,2.5,5,7.5])box(.1,podium-.5,.18,x,podium/2,8.38,2);
    for(const x of [-9.8,9.8])box(.55,podium,.65,x,podium/2,8.05,0);
    box(18,.22,2.4,0,step*1.12,7.3,2);
    box(21.9,.2,16.9,0,podium-.1,0,0);
    const upper=roofHeight-podium;
    if(upper>0)box(18.4,upper,13.6,0,podium+upper/2,-1);
    for(let floor=2;floor<n;floor++){
      const y=floor*step+step*.53;
      for(const z of [-7.84,5.84]){
        box(17.6,step*.57,.1,0,y,z,1);
        for(let bay=-4;bay<=4;bay++)box(.09,step*.59,.16,bay*2,y,z,2);
      }
      for(const x of [-9.24,9.24])box(.1,step*.57,12.7,x,y,-1,1);
      box(18.7,.18,13.9,0,(floor+1)*step-.1,-1,0);
    }
    for(const x of [-10.84,10.84])box(.1,podium*.55,11.8,x,podium*.54,-1,1);
  }else if(!lab){
    box(21.6,roofHeight,16.6,0,roofHeight/2,0);
    // Tall glazed entry with stone piers; upper floors remain ordinary offices.
    box(7,Math.min(step*1.65,5),.16,0,Math.min(step*1.65,5)/2,8.4,1);
    for(const x of [-3.65,3.65])box(.4,Math.min(step*1.7,5.2),.5,x,Math.min(step*1.7,5.2)/2,8.1,4);
    for(let floor=0;floor<n;floor++){
      const y=floor*step+step*.54;
      for(let bay=-4;bay<=4;bay++)for(const side of [-1,1]){
        if(floor<2&&side===1&&Math.abs(bay)<=1)continue;
        box(1.65,step*.65,.08,bay*2.25,y,side*8.34,1);
        box(.06,step*.65,.12,bay*2.25,y,side*8.36,2);
      }
      for(let bay=-3;bay<=3;bay++)for(const side of [-1,1])box(.08,step*.65,1.5,side*10.84,y,bay*2.2,1);
      box(21.9,.13,16.9,0,(floor+1)*step-.1,0,2);
    }
    // Narrow vertical mullions, not residential balconies or oversized window frames.
    for(const x of [-9,-4.5,4.5,9])box(.13,roofHeight,.13,x,roofHeight/2,8.42,0);
    box(8,.15,2,0,Math.min(step*1.7,5.2),7.5,2);
  }else{
    // Two laboratory wings and a recessed, glazed circulation core.
    for(const x of [-7.5,7.5])box(6.6,roofHeight,16.6,x,roofHeight/2,0);
    box(8.4,roofHeight,11.5,0,roofHeight/2,-2.55);
    box(7.8,roofHeight-.3,.12,0,(roofHeight-.3)/2,3.27,1);
    for(let floor=0;floor<n;floor++){
      const y=floor*step+step*.55;
      for(const x of [-7.5,7.5]){
        for(const z of [-8.34,8.34]){
          box(5.7,step*.51,.1,x,y,z,1);
          for(const dx of [-1.9,0,1.9])box(.08,step*.54,.16,x+dx,y,z,2);
          box(6.7,.17,.52,x,y+step*.3,z>0?8.15:-8.15,0);
        }
        box(6.7,.18,16.8,x,(floor+1)*step-.13,0,2);
      }
      for(const side of [-1,1])for(let bay=-3;bay<=3;bay++)box(.1,step*.51,1.7,side*10.84,y,bay*2.2,1);
      box(8.4,.22,11.6,0,(floor+1)*step-.15,-2.55,2);
    }
    for(const x of [-2.8,0,2.8])box(.13,roofHeight,.18,x,roofHeight/2,3.36,2);
    box(7,.15,2.5,0,3.1,4.5,2);
    // Enclosed service entrance, not invented operational HVAC equipment.
    box(.16,2.5,2.3,10.95,1.25,-5,3);
    for(let slat=0;slat<9;slat++)box(.2,.06,2.3,10.97,.3+slat*.25,-5,2);
  }
  // Roof plane retains the prior model's centre support elevation for existing PV.
  if(lab){for(const x of [-7.5,7.5])box(6.6,.15,16.6,x,roofHeight-.075,0,3);box(8.4,.15,11.5,0,roofHeight-.075,-2.55,3);}
  else if(service&&n>2)box(18.4,.15,13.6,0,roofHeight-.075,-1,3);
  else box(21.6,.15,16.6,0,roofHeight-.075,0,3);
  const parapet=Math.max(0,height-roofHeight);
  const setback=service&&n>2;
  for(const z of setback?[-7.9,5.9]:[-8.4,8.4])box(setback?18.8:22,parapet,.2,0,roofHeight+parapet/2,z,2);
  for(const x of setback?[-9.3,9.3]:[-10.9,10.9])box(.2,parapet,setback?14:17,x,roofHeight+parapet/2,setback?-1:0,2);
  // Lab's front recess stays open; remove the spanning front parapet.
  if(lab){const array=batches[2];const index=array.findIndex(m=>m.elements[12]===0&&m.elements[14]===8.4&&m.elements[0]===22);if(index>=0)array.splice(index,1);}
  batches.forEach((matrices,i)=>{
    const mesh=new THREE.InstancedMesh(new THREE.BoxGeometry(1,1,1),materials[i],matrices.length);
    matrices.forEach((matrix,index)=>mesh.setMatrixAt(index,matrix));mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);
  });
  group.userData.architecture=service?'SERVICE_TERRACE':lab?'LAB_WINGS':'OFFICE_GRID';group.userData.floorCount=n;
  group.updateMatrixWorld(true);return group;
}
