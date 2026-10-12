import {http} from './http';import type {DataSourceStatus,ProviderStatus,SystemHealth,SystemOverview,SystemTaskSummary,SystemTraceability} from '@/types'
export const systemApi={
 health:()=>http.get<never,SystemHealth>('/api/system/health'),
 overview:(enterprise_id?:number)=>http.get<never,SystemOverview>('/api/system/overview',{params:{enterprise_id}}),
 providers:(enterprise_id?:number)=>http.get<never,ProviderStatus[]>('/api/system/providers',{params:{enterprise_id}}),
 dataSources:(enterprise_id?:number)=>http.get<never,DataSourceStatus[]>('/api/system/data-sources',{params:{enterprise_id}}),
 tasks:(enterprise_id?:number)=>http.get<never,SystemTaskSummary[]>('/api/system/tasks',{params:{enterprise_id}}),
 trace:(params:{scenario_version_id?:number;data_source_id?:number})=>http.get<never,SystemTraceability>('/api/system/trace',{params})
}
