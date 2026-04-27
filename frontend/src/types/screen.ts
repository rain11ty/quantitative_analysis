export type ScreenCompareMode = 'field' | 'value';

export interface ScreenFieldOption {
  value: string;
  label: string;
}

export interface ScreenQueryForm {
  industry: string;
  area: string;
  market: string;
  trade_date: string;
  pe_min: string;
  pe_max: string;
  pb_min: string;
  pb_max: string;
  ps_min: string;
  ps_max: string;
  dv_min: string;
  dv_max: string;
  mv_min: string;
  mv_max: string;
  circ_mv_min: string;
  circ_mv_max: string;
  turnover_min: string;
  turnover_max: string;
  volume_ratio_min: string;
  volume_ratio_max: string;
  rsi6_min: string;
  rsi6_max: string;
  kdj_k_min: string;
  kdj_k_max: string;
  macd_min: string;
  macd_max: string;
  cci_min: string;
  cci_max: string;
  net_amount_min: string;
  net_amount_max: string;
  lg_buy_rate_min: string;
  lg_buy_rate_max: string;
  net_d5_amount_min: string;
  net_d5_amount_max: string;
}

export interface ScreenDynamicConditionForm {
  id: number;
  fieldA: string;
  operator: string;
  compareMode: ScreenCompareMode;
  fieldB: string;
  value: string;
}

export interface ScreenDynamicConditionPayload {
  field_a: string;
  operator: string;
  field_b?: string;
  value?: number;
}

export type ScreenSubmissionPayload = Partial<ScreenQueryForm> & {
  page: number;
  page_size: number;
  dynamic_conditions?: ScreenDynamicConditionPayload[];
};

export interface MarketHealthPayload {
  success?: boolean;
  latest_trade_date?: string | null;
  message?: string | null;
}

export interface ScreenStockRow {
  ts_code: string;
  symbol?: string | null;
  name?: string | null;
  industry?: string | null;
  area?: string | null;
  trade_date?: string | null;
  list_date?: string | null;
  daily_close?: number | null;
  pe?: number | null;
  pb?: number | null;
  ps?: number | null;
  total_mv?: number | null;
  circ_mv?: number | null;
  turnover_rate?: number | null;
  volume_ratio?: number | null;
  factor_pct_change?: number | null;
  factor_rsi_6?: number | null;
  factor_kdj_k?: number | null;
  factor_macd?: number | null;
  factor_cci?: number | null;
  moneyflow_net_amount?: number | null;
  moneyflow_buy_lg_amount_rate?: number | null;
  moneyflow_net_d5_amount?: number | null;
}

export interface ScreenResultPayload {
  stocks?: ScreenStockRow[];
  total?: number;
  has_more?: boolean;
  page?: number;
  page_size?: number;
  error?: string | null;
}
