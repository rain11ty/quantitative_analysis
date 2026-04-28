import { apiGet, apiPost } from '../../lib/http';
import type { ApiResponse, StockDetail, HistoryItem, FactorItem, MoneyflowItem, CyqPerfItem, CyqChipItem } from '../../types/stock';

export function getStockInfo(tsCode: string) { return apiGet<ApiResponse<StockDetail>>('/api/stocks/' + tsCode); }
export function getRealtime(tsCode: string, freq = 'daily') { return apiGet<ApiResponse<Record<string, unknown>>>('/api/stocks/' + tsCode + '/realtime', { freq }); }
export function getHistory(tsCode: string, params: Record<string, unknown>) { return apiGet<ApiResponse<HistoryItem[]>>('/api/stocks/' + tsCode + '/history', params); }
export function getFactors(tsCode: string, limit = 750) { return apiGet<ApiResponse<FactorItem[]>>('/api/stocks/' + tsCode + '/factors', { limit }); }
export function getMoneyflow(tsCode: string, limit = 250) { return apiGet<ApiResponse<MoneyflowItem[]>>('/api/stocks/' + tsCode + '/moneyflow', { limit }); }
export function getCyqPerf(tsCode: string, limit = 250) { return apiGet<ApiResponse<CyqPerfItem[]>>('/api/stocks/' + tsCode + '/cyq', { limit }); }
export function getCyqChips(tsCode: string, limitDays = 5) { return apiGet<ApiResponse<CyqChipItem[]>>('/api/stocks/' + tsCode + '/cyq_chips', { limit_days: limitDays }); }
export function addToWatchlist(tsCode: string) { return apiPost('/api/watchlist/' + tsCode); }
export function saveAnalysisRecord(tsCode: string, data: Record<string, unknown>) { return apiPost('/api/auth/profile/records/analysis', { ts_code: tsCode, ...data }); }
