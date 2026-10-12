import {http,silentConfig} from './http'
import type {LoadStatistics,RecommendationConversionRequest,RecommendationConversionResult,RecommendationRequest,RecommendationRun,WeatherHourlyPoint,WeatherStatisticsSummary} from '@/types'
export const recommendationsApi={
 catalog:()=>http.get<never,MeasureCatalog>('/api/recommendations/measure-catalog'),
 list:(enterpriseId?:number)=>http.get<never,RecommendationRun[]>('/api/recommendations/low-carbon-paths',{params:{enterprise_id:enterpriseId}}),
 get:(id:number)=>http.get<never,RecommendationRun>(`/api/recommendations/low-carbon-paths/${id}`),
 create:(payload:RecommendationRequest)=>http.post<never,RecommendationRun>('/api/recommendations/low-carbon-paths',payload,{...silentConfig,timeout:120000}),
 convert:(id:number,payload:RecommendationConversionRequest)=>http.post<never,RecommendationConversionResult>(`/api/recommendations/paths/${id}/convert-to-scenario`,payload),
 loadStatistics:(enterpriseId:number,start:string,end:string,timezone:string)=>http.get<never,LoadStatistics>('/api/loads/statistics',{params:{enterprise_id:enterpriseId,start,end,timezone}}),
 weatherStatistics:(siteId:number,start:string,end:string,timezone:string)=>http.get<never,WeatherStatisticsSummary>('/api/weather/statistics',{params:{site_id:siteId,start,end,timezone}}),
 weatherHourly:(siteId:number,start:string,end:string,timezone:string)=>http.get<never,{items:WeatherHourlyPoint[]}>('/api/weather/hourly',{params:{site_id:siteId,start,end,timezone}})
}
export interface MeasureCatalogItem{measure_code:string;measure_name:string;enabled:boolean;recommendation_status:string;parameter_sources:Record<string,string>;experiment_parameters:Record<'LOW'|'MEDIUM'|'HIGH',Record<string,unknown>>}
export interface MeasureCatalog{schema_version:string;baseline_scenario_version_id:number;site_code:string;measures:MeasureCatalogItem[];combination_rules:{combination:string[];allowed:boolean;rule:string}[]}
