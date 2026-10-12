import {http} from './http'
import type {RiskAssessment,RiskAssessmentCreate} from '@/types'
export const risksApi={
 get:(id:number)=>http.get<never,RiskAssessment>(`/api/risk-assessments/${id}`),
 list:(params?:{scenario_version_id?:number;simulation_task_id?:number;start?:string;end?:string})=>http.get<never,RiskAssessment[]>('/api/risk-assessments',{params}),
 create:(payload:RiskAssessmentCreate)=>http.post<never,RiskAssessment>('/api/risk-assessments',payload)
}
