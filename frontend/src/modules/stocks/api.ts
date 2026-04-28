import { apiGet } from '../../lib/http';

export function getIndustries() { return apiGet<{ data: { industry: string }[] }>('/api/industries'); }
export function getAreas() { return apiGet<{ data: { area: string }[] }>('/api/areas'); }
export function getStockList(params: Record<string, unknown>) { return apiGet<{ data: Record<string, unknown>[]; total: number; has_more: boolean }>('/api/stocks', params); }
