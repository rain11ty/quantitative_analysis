import { apiGet, apiPost, apiDelete } from '../../lib/http';

export interface BacktestResult {
  strategy_name?: string; ts_code?: string; start_date?: string; end_date?: string;
  initial_capital?: number; final_capital?: number; total_return?: number;
  annual_return?: number; sharpe_ratio?: number; max_drawdown?: number;
  win_rate?: number; volatility?: number; total_commission?: number;
  avg_hold_days?: number; trades?: Record<string, unknown>[];
}

export interface BacktestRecord {
  id: number; strategy_name: string; ts_code: string;
  total_return: number; sharpe_ratio: number; max_drawdown: number;
  created_at: string;
}

export function searchStocks(keyword: string) { return apiGet<{ data: Record<string, unknown>[] }>('/api/stocks', { search: keyword, page_size: 10 }); }
export function runBacktest(data: Record<string, unknown>) { return apiPost<BacktestResult>('/api/analysis/backtest', data); }
export function getBacktestHistory(page: number, limit = 10) { return apiGet<{ data: BacktestRecord[]; total: number }>('/api/user/backtests', { page, limit }); }
export function deleteBacktest(id: number) { return apiDelete<{ code: number }>('/api/user/backtests/' + id); }
