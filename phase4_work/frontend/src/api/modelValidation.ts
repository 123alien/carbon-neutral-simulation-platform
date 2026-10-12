import {http} from './http'
import type {ModelValidationDetail,ModelValidationSummary} from '@/types'
export const modelValidationApi={list:()=>http.get<never,ModelValidationSummary[]>('/api/model-validation'),detail:(model:'WIND'|'PV')=>http.get<never,ModelValidationDetail>(`/api/model-validation/${model}`)}
