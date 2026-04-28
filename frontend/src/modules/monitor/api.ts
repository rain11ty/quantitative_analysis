import { apiGet } from '../../lib/http';

export function getMonitorDashboard(codes: string) { return apiGet<Record<string, unknown>>('/api/monitor/dashboard', { ts_codes: codes, include_detail: 1 }); }
export function getRanking(sortBy = 'pct_change', limit = 20) { return apiGet<{ data: Record<string, unknown>[] }>('/api/monitor/ranking', { sort_by: sortBy, limit }); }
export function getIntraday(tsCode: string, period = 5) { return apiGet<Record<string, unknown>>('/api/monitor/intraday/' + tsCode, { period }); }
export function getShock(tsCode?: string, limit = 30) { return apiGet<{ data: Record<string, unknown>[] }>('/api/monitor/shock', tsCode ? { ts_code: tsCode, limit } : { limit }); }
export function searchStocks(keyword: string) { return apiGet<{ data: Record<string, unknown>[] }>('/api/stocks', { search: keyword, page_size: 10 }); }
