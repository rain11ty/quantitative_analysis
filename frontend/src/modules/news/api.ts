import { apiGet } from '../../lib/http';

export interface NewsItem { title: string; source: string; url: string; time: string; summary?: string }
export function getNews(source?: string) { return apiGet<{ data: NewsItem[]; total?: number }>('/api/news', source ? { source } : {}); }
