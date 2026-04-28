export function toNumber(value: unknown): number {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

export function formatNumber(value: unknown, decimals = 2): string {
  if (value === null || value === undefined || value === '') {
    return '--';
  }

  const num = Number(value);
  if (!Number.isFinite(num)) {
    return '--';
  }

  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatPercent(value: unknown, decimals = 2, showSign = true): string {
  if (value === null || value === undefined || value === '') {
    return '--';
  }

  const num = Number(value);
  if (!Number.isFinite(num)) {
    return '--';
  }

  const sign = showSign && num > 0 ? '+' : '';
  return `${sign}${num.toFixed(decimals)}%`;
}

export function formatCompactNumber(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '--';
  }

  const num = Number(value);
  if (!Number.isFinite(num)) {
    return '--';
  }

  const abs = Math.abs(num);
  if (abs >= 1e8) {
    return `${(num / 1e8).toFixed(2)}亿`;
  }
  if (abs >= 1e4) {
    return `${(num / 1e4).toFixed(2)}万`;
  }
  return num.toLocaleString('zh-CN');
}

export function formatMarketLabel(tsCode: string): string {
  if (tsCode.endsWith('.SH')) {
    return '上海';
  }
  if (tsCode.endsWith('.BJ')) {
    return '北交所';
  }
  if (tsCode.endsWith('.SZ')) {
    return '深圳';
  }
  return '未知市场';
}

export function formatMarketTone(tsCode: string): string {
  if (tsCode.endsWith('.SH')) {
    return 'danger';
  }
  if (tsCode.endsWith('.BJ')) {
    return 'warning';
  }
  return 'success';
}

export function normalizeTradeDate(value: unknown): string {
  return String(value ?? '').replace(/-/g, '');
}

export function formatTradeDate(value: unknown): string {
  const normalized = normalizeTradeDate(value);
  if (normalized.length !== 8) {
    return String(value ?? '--');
  }

  return `${normalized.slice(0, 4)}-${normalized.slice(4, 6)}-${normalized.slice(6, 8)}`;
}

export function average(values: number[]): number {
  const valid = values.filter((item) => Number.isFinite(item) && item > 0);
  if (!valid.length) {
    return 0;
  }
  return valid.reduce((sum, item) => sum + item, 0) / valid.length;
}

export function movingAverage(values: number[], size: number): Array<number | null> {
  return values.map((_, index) => {
    if (index < size - 1) {
      return null;
    }

    const window = values.slice(index - size + 1, index + 1);
    const total = window.reduce((sum, item) => sum + item, 0);
    return Number((total / size).toFixed(2));
  });
}
