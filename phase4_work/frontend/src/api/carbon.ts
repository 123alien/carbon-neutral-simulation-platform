import {http} from './http'
import type {CarbonAccountingRun,CarbonAccountingResult,CarbonStatistics,CarbonTrendResponse,OrganizationNode} from '@/types'
export interface StandardMapping{energy_type:string;boundary:string;activity_value:number;activity_unit:string;factor:number;factor_unit:string;formula:string;emission_t:number;data_class:string}
export interface StandardApplicability{object_type:string;general_standard:string;industry_series:string;industry_profile:string|null;status:'NOT_DIRECTLY_APPLICABLE'|'INDUSTRY_PROFILE_REQUIRED';reason:string;selection_locked:boolean;official_catalog:string;review_required:boolean}
export interface AccountingStandardValidation{standard:string;claim:string;boundary:string;applicability:StandardApplicability;mapping:StandardMapping[];recalculable_example:StandardMapping;total_emission_t:number;data_notice:string}
export interface RegionalCarbonSite{site_id:number;site_name:string;site_type:string;total_emission_t:number|null;trend:Array<{timestamp:string;emission_t:number}>;data_status:string}
export interface RegionalCarbonSummary{enterprise_id:number;region_name:string;data_class:string;data_notice:string;site_count:number;total_emission_t:number;sites:RegionalCarbonSite[]}
export interface CarbonFilters{start_time?:string;end_time?:string;granularity?:'day'|'month'|'year';energy_type?:string;scope?:string;building?:number;device?:number}
export const carbonApi={
 site:(id:number,params?:CarbonFilters)=>http.get<never,CarbonTrendResponse>(`/api/sites/${id}/carbon`,{params}),
 siteStatistics:(id:number,params?:CarbonFilters)=>http.get<never,CarbonTrendResponse>(`/api/sites/${id}/carbon/statistics`,{params}),
 building:(id:number,params?:Omit<CarbonFilters,'building'>)=>http.get<never,CarbonTrendResponse>(`/api/buildings/${id}/carbon`,{params}),
 runs:(params?:{enterprise_id?:number;start_time?:string;end_time?:string;status?:string})=>http.get<never,CarbonAccountingRun[]>('/api/carbon-accounting/runs',{params}),
 run:(id:number)=>http.get<never,CarbonAccountingRun>(`/api/carbon-accounting/runs/${id}`),
 results:(id:number,params?:{energy_type?:string;scope?:string;device_id?:number;organization_node_id?:number;start_time?:string;end_time?:string})=>http.get<never,CarbonAccountingResult[]>(`/api/carbon-accounting/runs/${id}/results`,{params}),
 statistics:(id:number,params:{granularity:'day'|'month'|'year';dimension:'energy'|'device'|'organization'|'organization_level'|'scope';timezone?:string;energy_type?:string;scope?:string;organization_node_id?:number;start_time?:string;end_time?:string})=>http.get<never,CarbonStatistics>(`/api/carbon-accounting/runs/${id}/statistics`,{params}),
 organizations:(enterpriseId:number)=>http.get<never,OrganizationNode[]>('/api/organizations',{params:{enterprise_id:enterpriseId}}),
 standardValidation:()=>http.get<never,AccountingStandardValidation>('/api/acceptance-demo/accounting-standard'),
 regionalCarbon:(enterpriseId:number)=>http.get<never,RegionalCarbonSummary>('/api/acceptance-demo/regional-carbon',{params:{enterprise_id:enterpriseId}})
}
