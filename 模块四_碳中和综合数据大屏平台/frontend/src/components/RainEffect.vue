<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount,watch} from 'vue'
const props=defineProps<{precipitation?:number|null}>()
const host=ref<HTMLCanvasElement>(),frames=ref(0),running=ref(false)
let context:CanvasRenderingContext2D|null=null,resize:ResizeObserver,intersection:IntersectionObserver,media:MediaQueryList,visible=false,disposed=false,frame=0,last=0,width=0,height=0,elapsed=0
// Fixed screen-space seeds: decorative precipitation, never GIS positions or business data.
const drops=Array.from({length:220},(_,i)=>{
 const depth=((i*37)%101)/101
 return {x:((i*73)%223)/223,y:((i*47)%227)/227,
  speed:180+(i%7)*35,
  alpha:.15+(i%5)*.055,radius:.55+depth*.65,
  slant:.035+(i%11)*.009,phase:i*1.73}
})
function draw(dt=0){if(!context)return;elapsed+=dt;context.clearRect(0,0,width,height);const count=Math.min(220,Math.max(100,Math.round(115+Math.max(0,props.precipitation??.1)*35)))
 for(let i=0;i<count;i++){
  const d=drops[i],y=(d.y*(height+20)+elapsed*d.speed)%(height+20)-10
  const sway=Math.sin(elapsed*.65+d.phase)*2
  const x=(d.x*(width+40)-elapsed*d.speed*d.slant+sway)%(width+40),px=x< -10?x+width+40:x
  // Compact falling droplets only: no line segments or slash-shaped streaks.
  context.fillStyle=`rgba(220,241,250,${d.alpha})`
  context.beginPath();context.ellipse(px,y,d.radius,d.radius*1.65,0,0,Math.PI*2);context.fill()
 }
 frames.value++
}
function tick(now:number){frame=0;if(disposed||!visible||document.hidden||media.matches){running.value=false;return}if(!last||now-last>=1000/30){draw(last?Math.min(.1,(now-last)/1000):0);last=now}frame=requestAnimationFrame(tick)}
function sync(){cancelAnimationFrame(frame);frame=0;last=0;running.value=!disposed&&visible&&!document.hidden&&!media.matches;if(running.value)frame=requestAnimationFrame(tick);else if(visible&&!document.hidden)draw()}
watch(()=>props.precipitation,()=>{if(!running.value)draw()})
onMounted(()=>{if(!host.value)return;context=host.value.getContext('2d');media=matchMedia('(prefers-reduced-motion: reduce)');resize=new ResizeObserver(()=>{if(!host.value)return;const r=host.value.getBoundingClientRect();width=r.width;height=r.height;host.value.width=Math.round(width);host.value.height=Math.round(height);if(width&&height)draw()});resize.observe(host.value);intersection=new IntersectionObserver(entries=>{visible=entries[0]?.isIntersecting??false;sync()});intersection.observe(host.value);document.addEventListener('visibilitychange',sync);media.addEventListener('change',sync)})
onBeforeUnmount(()=>{disposed=true;cancelAnimationFrame(frame);resize?.disconnect();intersection?.disconnect();document.removeEventListener('visibilitychange',sync);media?.removeEventListener('change',sync);context?.clearRect(0,0,width,height)})
</script>
<template><canvas ref="host" class="twin-rain" data-testid="dynamic-rain" :data-running="running" :data-rain-frames="frames" aria-hidden="true"/></template>
<style scoped>.twin-rain{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;opacity:1;mask-image:linear-gradient(transparent,#000 12%,#000 88%,transparent)}</style>
