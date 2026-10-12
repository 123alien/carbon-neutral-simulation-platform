import * as THREE from 'three';

/** Keep a glTF's own transforms; normalize using an outer placement node. */
export function normalizeAsset(asset: THREE.Object3D, dimensions: THREE.Vector3, uniform = false) {
  const root = new THREE.Group();
  root.add(asset);
  root.updateMatrixWorld(true);
  const size = new THREE.Box3().setFromObject(root).getSize(new THREE.Vector3());
  if (Math.min(size.x, size.y, size.z) <= 0) throw new Error('模型几何尺寸无效');
  if (uniform) root.scale.setScalar(dimensions.y / size.y);
  else root.scale.set(dimensions.x / size.x, dimensions.y / size.y, dimensions.z / size.z);
  root.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(root), center = bounds.getCenter(new THREE.Vector3());
  root.position.set(-center.x, -bounds.min.y, -center.z);
  const placement = new THREE.Group();
  placement.add(root);
  placement.updateMatrixWorld(true);
  return placement;
}

export function disposeObject(root: THREE.Object3D) {
  const materials = new Set<THREE.Material>(), textures = new Set<THREE.Texture>();
  root.traverse(node => {
    const mesh = node as THREE.Mesh;
    mesh.geometry?.dispose();
    for (const material of (Array.isArray(mesh.material) ? mesh.material : [mesh.material])) {
      if (!material) continue;
      materials.add(material);
      for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
    }
  });
  textures.forEach(t => t.dispose()); materials.forEach(m => m.dispose());
}

/** Presentation landscaping only: not survey geometry or additional business assets. */
export function campusEnvironment(positions: {x:number;y:number;z:number}[], devices: {x:number;y:number;z:number;type:string}[] = []) {
  const group = new THREE.Group();
  if (!positions.length) return group;
  const minX=Math.min(...positions.map(p=>p.x))-27, maxX=Math.max(...positions.map(p=>p.x))+27;
  const minZ=Math.min(...positions.map(p=>p.z))-25, maxZ=Math.max(...positions.map(p=>p.z))+27;
  const width=maxX-minX, depth=maxZ-minZ, cx=(minX+maxX)/2, cz=(minZ+maxZ)/2;
  const material=(color:number)=>new THREE.MeshStandardMaterial({color,roughness:.92});
  const grass=material(0x7b9d72),stone=material(0xd5d9ce),asphalt=material(0x45535a),white=material(0xe8ece7);
  function slab(w:number,d:number,x:number,z:number,m:THREE.Material,y=.03) {
    const o=new THREE.Mesh(new THREE.BoxGeometry(w,.08,d),m);o.position.set(x,y,z);o.receiveShadow=true;group.add(o);return o;
  }
  slab(width+22,depth+22,cx,cz,grass,-.12);
  for (const z of [minZ,maxZ]) { slab(width+10,9,cx,z,stone); slab(width+9,6.5,cx,z,asphalt,.09);
    for(let x=minX;x<maxX;x+=7) slab(3,.13,x,z,white,.15); }
  for(const x of [minX,maxX]) { slab(9,depth,x,cz,stone);slab(6.5,depth,x,cz,asphalt,.09);
    for(let z=minZ+6;z<maxZ-3;z+=7) slab(.13,3,x,z,white,.15); }
  // Only place the cross-campus road in an actual gap between building rows.
  const zs=[...new Set(positions.map(p=>p.z))].sort((a,b)=>a-b);
  let corridor: number|undefined;
  for(let i=1;i<zs.length;i++) if(zs[i]-zs[i-1]>30) corridor=(zs[i]+zs[i-1])/2;
  if(corridor!==undefined) { slab(width,8,cx,corridor,stone);slab(width,5.5,cx,corridor,asphalt,.09);
    for(let x=minX+6;x<maxX-3;x+=7) slab(3,.13,x,corridor,white,.15); }
  const wood=material(0x756651),leaves=[material(0x366c50),material(0x56815b),material(0x638862)];
  function tree(x:number,z:number,i:number) {
    if(devices.some(p=>Math.abs(p.x-x)<7&&Math.abs(p.z-z)<8))return;
    const trunk=new THREE.Mesh(new THREE.CylinderGeometry(.12,.2,2.2,7),wood);trunk.position.set(x,1.1,z);
    const canopy=new THREE.Mesh(new THREE.IcosahedronGeometry(1.35,1),leaves[i%3]);canopy.scale.set(1,1.35,1);canopy.position.set(x,3,z);canopy.castShadow=true;group.add(trunk,canopy);
  }
  for(let x=minX+9,i=0;x<maxX-5;x+=7,i++) {tree(x,minZ+7,i);tree(x,maxZ-7,i+1);}
  for(let z=minZ+15,i=0;z<maxZ-9;z+=7,i++) {tree(minX+7,z,i);tree(maxX-7,z,i+1);}
  for(const p of positions) {
    slab(28,23,p.x,p.z,stone,p.y-.035);
    if(corridor!==undefined) {const edge=p.z>corridor?p.z-11.5:p.z+11.5;const roadEdge=corridor+(p.z>corridor?4:-4);
      slab(3,Math.abs(edge-roadEdge),p.x,(edge+roadEdge)/2,stone);
      for(let stripe=-2;stripe<=2;stripe++)slab(2.8,.4,p.x,corridor+stripe*.8,white,.15);
    }
  }
  for(const p of devices) {
    if(p.type.includes('CHARG')||p.type.includes('EV')) {
      slab(11,7,p.x,p.z+2,asphalt,.08);
      for(let slot=-2;slot<=2;slot++)slab(.1,5.5,p.x+slot*2.3,p.z+2,white,.15);
      slab(9.3,.1,p.x,p.z+4.8,white,.15);
    } else if(p.type.includes('STORAGE')) {
      slab(8,5,p.x,p.z,stone,-.035);
      // Protective bollards mark the maintenance zone without implying equipment.
      const yellow=material(0xd6b34e);
      for(const x of [-3.5,3.5])for(const z of [-1.9,1.9]){
        const bollard=new THREE.Mesh(new THREE.CylinderGeometry(.11,.11,.75,8),yellow);bollard.position.set(p.x+x,.375,p.z+z);group.add(bollard);
      }
    } else if(p.type.includes('WIND'))slab(3,3,p.x,p.z,stone,-.035);
  }
  return group;
}
