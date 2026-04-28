import { apiGet } from '../../lib/http';

export interface IndexKlineItem {
  trade_date?: string; open?: number; close?: number; high?: number; low?: number; vol?: number;
}
export interface MarketOverview {
  indices?: { ts_code: string; name: string; price: number; change: number; pct_chg: number }[];
  breadth?: { up: number; down: number; flat: number };
  summary?: { total_turnover: number; total_volume: number; limit_up: number; limit_down: number; trade_date: string };
}
export interface MarketHealth { success: boolean; latest_trade_date?: string; message?: string; proxy_url?: string }

export function getMarketOverview() { return apiGet<MarketOverview>('/api/market/overview'); }
export function getIndexKline(code: string, period: string) { return apiGet<{ data: IndexKlineItem[] }>('/api/market/index/' + code + '/kline', { period }); }
export function getMarketHealth() { return apiGet<MarketHealth>('/api/market/health'); }
