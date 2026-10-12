import {http} from './http';import type {ReportCreateRequest,ReportFile,ReportTask} from '@/types'
export const reportsApi={
 list:(params?:{site_id?:number;scenario_version_id?:number;simulation_task_id?:number;status?:string;start?:string;end?:string})=>http.get<never,ReportTask[]>('/api/reports',{params}),
 get:(id:number)=>http.get<never,ReportTask>(`/api/reports/feasibility/${id}`),
 create:(payload:ReportCreateRequest)=>http.post<never,ReportTask>('/api/reports/feasibility',payload),
 render:(id:number,formats:('DOCX'|'PDF')[])=>http.post<never,ReportFile[]>(`/api/reports/${id}/render`,{formats}),
 downloads:(id:number)=>http.get<never,ReportFile[]>(`/api/reports/${id}/downloads`),
 download:(id:number,format:'DOCX'|'PDF')=>http.get<never,Blob>(`/api/reports/${id}/download/${format.toLowerCase()}`,{responseType:'blob'})
}
