export interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export interface DailyBasic {
  close?: number | null;
  circ_mv?: number | null;
  dv_ratio?: number | null;
  pb?: number | null;
  pe_ttm?: number | null;
  ps_ttm?: number | null;
  total_mv?: number | null;
  trade_date?: string | null;
  turnover_rate?: number | null;
  volume_ratio?: number | null;
}

export interface StockDetail {
  area?: string | null;
  daily_basic?: DailyBasic | null;
  industry?: string | null;
  list_date?: string | null;
  name?: string | null;
  symbol?: string | null;
  ts_code: string;
}

export interface RealtimeSeriesItem {
  amount?: number | null;
  high?: number | null;
  label?: string | null;
  low?: number | null;
  open?: number | null;
  price?: number | null;
  close?: number | null;
  volume?: number | null;
}

export interface QuoteSnapshot {
  amount?: number | null;
  amplitude?: number | null;
  change?: number | null;
  high?: number | null;
  low?: number | null;
  name?: string | null;
  open?: number | null;
  pct_chg?: number | null;
  pre_close?: number | null;
  price?: number | null;
  source?: string | null;
  trade_date?: string | null;
  trade_time?: string | null;
  ts_code?: string | null;
  turnover_rate?: number | null;
  volume?: number | null;
}

export interface RealtimePayload {
  is_index?: boolean;
  is_watchlist?: boolean;
  quote?: QuoteSnapshot | null;
  quote_message?: string | null;
  quote_source?: string | null;
  series?: RealtimeSeriesItem[];
  series_mode?: 'daily' | 'weekly' | 'monthly' | string;
  updated_at?: string | null;
}

export interface HistoryItem {
  amount?: number | null;
  change_c?: number | null;
  close?: number | null;
  high?: number | null;
  low?: number | null;
  open?: number | null;
  pct_chg?: number | null;
  pre_close?: number | null;
  trade_date?: string | null;
  ts_code?: string | null;
  vol?: number | null;
}

export interface FactorItem extends HistoryItem {
  boll_lower?: number | null;
  boll_mid?: number | null;
  boll_upper?: number | null;
  cci?: number | null;
  kdj_d?: number | null;
  kdj_j?: number | null;
  kdj_k?: number | null;
  macd?: number | null;
  macd_dea?: number | null;
  macd_dif?: number | null;
  rsi_12?: number | null;
  rsi_24?: number | null;
  rsi_6?: number | null;
}

export interface MoneyflowItem {
  buy_elg_amount?: number | null;
  buy_lg_amount?: number | null;
  buy_md_amount?: number | null;
  buy_sm_amount?: number | null;
  net_mf_amount?: number | null;
  sell_elg_amount?: number | null;
  sell_lg_amount?: number | null;
  sell_md_amount?: number | null;
  sell_sm_amount?: number | null;
  trade_date?: string | null;
}

export interface CyqPerfItem {
  cost_15pct?: number | null;
  cost_50pct?: number | null;
  cost_5pct?: number | null;
  cost_85pct?: number | null;
  cost_95pct?: number | null;
  his_high?: number | null;
  his_low?: number | null;
  trade_date?: string | null;
  ts_code?: string | null;
  weight_avg?: number | null;
  winner_rate?: number | null;
}

export interface CyqChipItem {
  percent?: number | null;
  price?: number | null;
  trade_date?: string | null;
  ts_code?: string | null;
}
