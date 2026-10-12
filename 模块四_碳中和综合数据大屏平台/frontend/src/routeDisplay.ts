import type {ActivityPath} from './types'
export function sharedRoads(paths:ActivityPath[]){
 const edges:{a:number[];b:number[];id:string}[]=[],points=new Map<string,number[]>()
 const key=(p:number[])=>p.map(v=>v.toFixed(8)).join(',')
 for(const path of paths)for(const segment of path.segments||[])for(let i=1;i<segment.coordinates.length;i++){
  const a=segment.coordinates[i-1],b=segment.coordinates[i];if(key(a)===key(b))continue
  edges.push({a,b,id:path.global_id});points.set(key(a),a);points.set(key(b),b)
 }
 const parts=new Map<string,{coordinates:number[][];ids:Set<string>}>()
 for(const {a,b,id} of edges){
  const dx=b[0]-a[0],dy=b[1]-a[1],length=dx*dx+dy*dy
  const cuts=[{t:0,p:a},{t:1,p:b}]
  for(const p of points.values()){
   const t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/length
   if(t>1e-7&&t<1-1e-7&&Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)<1e-8)cuts.push({t,p})
  }
  cuts.sort((x,y)=>x.t-y.t)
  for(let i=1;i<cuts.length;i++){
   const p=cuts[i-1].p,q=cuts[i].p,k=[key(p),key(q)].sort().join('|');if(key(p)===key(q))continue
   if(!parts.has(k))parts.set(k,{coordinates:[p,q],ids:new Set()});parts.get(k)!.ids.add(id)
  }
 }
 return [...parts.values()]
}
