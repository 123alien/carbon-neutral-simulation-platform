import {http} from './http';import type {ImportConfirm,ImportPreview} from '@/types'
export type ImportKind='LOAD'|'WEATHER'|'PRICE'|'GRID_FACTOR'
const paths:Record<ImportKind,[string,string]>={LOAD:['/api/loads/hourly/import/preview','/api/loads/hourly/import/confirm'],WEATHER:['/api/weather/import/preview','/api/weather/import/confirm'],PRICE:['/api/market/prices/import/preview','/api/market/prices/import/confirm'],GRID_FACTOR:['/api/market/grid-factors/import/preview','/api/market/grid-factors/import/confirm']}
function form(file:File,options:Record<string,unknown>){const data=new FormData();data.append('file',file);data.append('options',JSON.stringify(options));return data}
export const importsApi={preview:(kind:ImportKind,file:File,options:Record<string,unknown>)=>http.post<never,ImportPreview>(paths[kind][0],form(file,options)),confirm:(kind:ImportKind,file:File,options:Record<string,unknown>)=>http.post<never,ImportConfirm>(paths[kind][1],form(file,options))}
