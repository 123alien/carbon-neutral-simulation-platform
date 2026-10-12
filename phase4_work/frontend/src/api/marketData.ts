import {http} from './http';import type {GreenPowerContract} from '@/types'
export type GreenPowerCreate=Omit<GreenPowerContract,'id'>
export const marketDataApi={contracts:(enterprise_id:number)=>http.get<never,GreenPowerContract[]>('/api/market/green-power/contracts',{params:{enterprise_id}}),createContract:(payload:GreenPowerCreate)=>http.post<never,GreenPowerContract>('/api/market/green-power/contracts',payload)}
