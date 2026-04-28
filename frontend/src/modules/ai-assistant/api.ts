import { http, apiGet, apiPost, apiPatch, apiDelete } from '../../lib/http';

export interface Conversation {
  id: number; title: string; summary?: string; created_at?: string; updated_at?: string; message_count?: number;
}
export interface ChatMessage {
  id: number; role: 'user' | 'assistant'; content: string; created_at?: string;
}

export function getConversations() { return apiGet<{ data: Conversation[] }>('/api/ai/conversations'); }
export function createConversation(title?: string) { return apiPost<{ data: Conversation }>('/api/ai/conversations', title ? { title } : {}); }
export function getMessages(convId: number) { return apiGet<{ data: ChatMessage[] }>('/api/ai/conversations/' + convId + '/messages'); }
export function renameConversation(convId: number, title: string) { return apiPatch<{ code: number }>('/api/ai/conversations/' + convId, { title }); }
export function deleteConversation(convId: number) { return apiDelete<{ code: number }>('/api/ai/conversations/' + convId); }

export function sendChatMessage(convId: number, content: string): Promise<Response> {
  return fetch('/api/ai/chat', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify({ conversation_id: convId, message: content }),
  });
}
