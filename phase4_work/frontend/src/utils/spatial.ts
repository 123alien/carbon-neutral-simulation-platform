import type {Building,Device,Site,SpatialCoordinate,SpatialSceneObject,SpatialValidation} from '@/types'
type SpatialEntity=Building|Device
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)
export function coordinateOf(entity:SpatialEntity,site:Site):SpatialCoordinate|null{
 const p=entity.position_json
 if(p&&finite(p.x)&&finite(p.y)){
  const hasZ=finite(p.z),x=p.x,y=hasZ?p.y:0,z=hasZ?(p.z as number):-p.y
  if(Math.abs(x)>1e7||Math.abs(y)>1e7||Math.abs(z)>1e7)return null
  return{x,y,z,source:'LOCAL'}
 }
 const lon=entity.longitude,lat=entity.latitude
 if(!finite(lon)||!finite(lat)||lon < -180||lon > 180||lat < -90||lat > 90||!finite(site.longitude)||!finite(site.latitude))return null
 const latScale=111320,lonScale=latScale*Math.cos(site.latitude*Math.PI/180)
 return{x:(lon-site.longitude)*lonScale,y:0,z:-(lat-site.latitude)*latScale,source:'GEOGRAPHIC'}
}
export function validateSpatial<T extends SpatialEntity>(items:T[],site:Site,kind:'BUILDING'|'DEVICE'):SpatialValidation{
 let invalidCount=0;const objects:SpatialSceneObject[]=[]
 for(const item of items){const coordinate=coordinateOf(item,site);if(!coordinate){invalidCount++;continue}objects.push({id:item.id,kind,name:item.name,type:kind==='BUILDING'?(item as Building).building_type:(item as Device).device_type,coordinate,source:item,quality:'NO_DATA'})}
 return{objects,invalidCount}
}
