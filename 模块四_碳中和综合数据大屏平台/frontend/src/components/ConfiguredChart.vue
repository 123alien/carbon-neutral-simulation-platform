<script setup lang="ts">
import {computed} from 'vue';
import Chart from './Chart.vue';
type Definition={id:string;title:string;type:'line'|'bar'|'gauge'|'sankey'|'radar';data_path:string;unit:string;bindings:any;refresh_seconds:number;interactions:string[];data_class:string};
const props=defineProps<{definition:Definition;source:any}>();
function path(source:any,value:string){return value.split('.').reduce((result,key)=>result?.[key],source)}
const dataset=computed(()=>path(props.source,props.definition.data_path));
const base={animationDuration:500,tooltip:{trigger:'item',backgroundColor:'rgba(5,31,43,.96)',borderColor:'#36cfc9',textStyle:{color:'#eaffff',fontSize:10}}};
const option=computed(()=>{
  const d=props.definition,b=d.bindings,data=dataset.value;
  if(d.type==='bar'){const rows=Array.isArray(data)?data:[];return {...base,grid:{left:75,right:12,top:10,bottom:20},xAxis:{type:'value',axisLabel:{color:'#83aab3'},splitLine:{lineStyle:{color:'#173f4a'}}},yAxis:{type:'category',inverse:true,data:rows.map(x=>String(x[b.category]??'').replace('湖北经济学院','')),axisLabel:{color:'#83aab3',fontSize:8}},series:[{type:'bar',data:rows.map(x=>x[b.value]),itemStyle:{color:'#51d8c8'},barMaxWidth:18}]}}
  if(d.type==='gauge')return {...base,series:[{type:'gauge',radius:'86%',startAngle:210,endAngle:-30,progress:{show:true,width:14,itemStyle:{color:'#51d8c8'}},axisLine:{lineStyle:{width:14,color:[[.4,'#275866'],[.7,'#bd9d3f'],[1,'#a84e49']]}},axisTick:{show:false},splitLine:{distance:-18,length:8,lineStyle:{color:'#8cb4ba'}},axisLabel:{distance:-34,color:'#8cb4ba',fontSize:8},pointer:{length:'55%',width:5},detail:{valueAnimation:true,formatter:`{value}${d.unit}`,color:'#efffff',fontSize:24,offsetCenter:[0,'55%']},data:[{value:Number(data||0),name:d.title,title:{color:'#8cb4ba',fontSize:10,offsetCenter:[0,'78%']}}]}]}
  if(d.type==='sankey')return {...base,series:[{type:'sankey',left:8,right:8,top:10,bottom:10,data:data?.[b.nodes]||[],links:(data?.[b.links]||[]).filter((x:any)=>Number(x[b.value])>0),nodeWidth:10,nodeGap:10,label:{color:'#bfe3e7',fontSize:8},lineStyle:{color:'gradient',opacity:.55},itemStyle:{borderColor:'#61e0d1',borderWidth:1}}]}
  if(d.type==='radar'){const rows=Array.isArray(data)?data:[];return {...base,radar:{radius:'65%',indicator:rows.map(x=>({name:x[b.indicator],max:b.maximum})),axisName:{color:'#9fc4ca',fontSize:9},splitLine:{lineStyle:{color:'#28535f'}},splitArea:{areaStyle:{color:['#092b39','#0c3441']}}},series:[{type:'radar',data:[{value:rows.map(x=>x[b.value]),name:d.title,areaStyle:{color:'rgba(67,219,201,.28)'},lineStyle:{color:'#50dfcf'},itemStyle:{color:'#f0c459'}}]}]}}
  const rows=Array.isArray(data)?data:[],series=b.series||[];
  return {...base,tooltip:{...base.tooltip,trigger:'axis'},legend:{top:0,textStyle:{color:'#a6cbd2',fontSize:9},data:series.map((x:any)=>x.name)},grid:{left:42,right:12,top:30,bottom:22},xAxis:{type:'category',data:rows.map(x=>x[b.x]),axisLabel:{color:'#83aab3',fontSize:8},axisLine:{lineStyle:{color:'#2c5965'}}},yAxis:{type:'value',axisLabel:{color:'#83aab3',fontSize:8},splitLine:{lineStyle:{color:'#173f4a'}}},series:series.map((s:any,index:number)=>({name:s.name,type:'line',data:rows.map(x=>x[s.field]),showSymbol:false,lineStyle:{width:index===1?3:2},itemStyle:{color:['#51e0cf','#f3c85f','#5fa9ff'][index%3]}}))}
});
</script>
<template><Chart :option="option"/></template>
