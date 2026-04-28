<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { useToast } from '../composables/useToast';
import { getConversations, createConversation, getMessages, renameConversation, deleteConversation, sendChatMessage, type Conversation, type ChatMessage } from '../modules/ai-assistant/api';

const toast = useToast();
const conversations = ref<Conversation[]>([]);
const activeConvId = ref<number | null>(null);
const messages = ref<ChatMessage[]>([]);
const inputText = ref('');
const sending = ref(false);
const convSearch = ref('');

const filteredConversations = computed(() => {
  if (!convSearch.value) return conversations.value;
  return conversations.value.filter(c => c.title?.toLowerCase().includes(convSearch.value.toLowerCase()));
});

onMounted(async () => {
  try {
    const res = await getConversations();
    conversations.value = res.data || [];
    if (conversations.value.length) { activeConvId.value = conversations.value[0].id; await loadMessages(activeConvId.value); }
  } catch { toast.error('对话列表加载失败'); }
});

async function loadMessages(convId: number) {
  try { const res = await getMessages(convId); messages.value = res.data || []; await nextTick(); scrollBottom(); } catch { toast.error('消息加载失败'); }
}
async function selectConv(conv: Conversation) { activeConvId.value = conv.id; await loadMessages(conv.id); }
async function newConv() {
  try { const res = await createConversation('新对话'); conversations.value.unshift(res.data); activeConvId.value = res.data.id; messages.value = []; } catch { toast.error('创建失败'); }
}

async function sendMessage() {
  const text = inputText.value.trim(); if (!text || sending.value) return;
  if (!activeConvId.value) await newConv(); if (!activeConvId.value) return;
  const convId = activeConvId.value;
  messages.value.push({ id: Date.now(), role: 'user', content: text, created_at: new Date().toISOString() });
  inputText.value = ''; sending.value = true;
  await nextTick(); scrollBottom();
  try {
    const response = await sendChatMessage(convId, text);
    if (response.ok && response.headers.get('content-type')?.includes('text/event-stream')) {
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      const assistantMsg: ChatMessage = { id: Date.now() + 1, role: 'assistant', content: '', created_at: new Date().toISOString() };
      messages.value.push(assistantMsg); let buffer = '';
      if (reader) {
        while (true) { const { done, value } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true }); const lines = buffer.split('\n'); buffer = lines.pop() || '';
          for (const line of lines) {
            if (line.startsWith('data: ')) { const data = line.slice(6); if (data === '[DONE]') continue;
              try { const p = JSON.parse(data); assistantMsg.content += p.content || p.message || p.delta || ''; } catch { assistantMsg.content += data; }
              await nextTick(); scrollBottom(); }
          }
        }
      }
    } else { const data = await response.json(); messages.value.push({ id: Date.now() + 1, role: 'assistant', content: data.data?.reply || data.message || '', created_at: new Date().toISOString() }); }
  } catch { messages.value.push({ id: Date.now() + 1, role: 'assistant', content: '请求失败，请重试', created_at: new Date().toISOString() }); toast.error('发送失败'); }
  sending.value = false; await nextTick(); scrollBottom();
  try { const res = await getConversations(); conversations.value = res.data || []; } catch { /* */ }
}

async function renameConv(conv: Conversation) { const title = prompt('新标题:', conv.title); if (title && title !== conv.title) { try { await renameConversation(conv.id, title); conv.title = title; } catch { toast.error('重命名失败'); } } }
async function removeConv(conv: Conversation) { if (!confirm('确定删除？')) return; try { await deleteConversation(conv.id); conversations.value = conversations.value.filter(c => c.id !== conv.id); if (activeConvId.value === conv.id) { activeConvId.value = conversations.value[0]?.id || null; if (activeConvId.value) await loadMessages(activeConvId.value); else messages.value = []; } toast.success('已删除'); } catch { toast.error('删除失败'); } }

function handleKeydown(e: KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }
function scrollBottom() { const el = document.getElementById('chat-msgs'); if (el) el.scrollTop = el.scrollHeight; }

function renderMarkdown(text: string): string {
  return text.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre style="background:#eef0f3;padding:12px;border-radius:8px;font-size:12px;overflow-x:auto;"><code>$2</code></pre>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code style="background:rgba(10,11,13,.05);padding:1px 5px;border-radius:4px;font-size:0.9em;">$1</code>').replace(/\n/g, '<br>');
}

const suggestions = ['分析上证指数走势', '推荐值得关注的股票', '什么是MACD金叉', '最近哪个行业强势', '如何构建量化策略'];
function useSuggestion(s: string) { inputText.value = s; sendMessage(); }
</script>

<template>
  <div style="display:flex;gap:0;height:calc(100vh - 160px);border-radius:var(--cb-radius-xl);overflow:hidden;border:1px solid var(--cb-border);background:var(--cb-white);">
    <div style="width:240px;min-width:240px;border-right:1px solid var(--cb-border);display:flex;flex-direction:column;background:var(--cb-gray);">
      <div style="padding:12px;"><button class="btn btn-primary w-full btn-sm" @click="newConv">+ 新对话</button></div>
      <div style="padding:0 12px 8px;"><input v-model="convSearch" class="form-input" placeholder="搜索..." style="font-size:12px;" /></div>
      <div style="flex:1;overflow-y:auto;padding:0 8px;">
        <div v-for="conv in filteredConversations" :key="conv.id" style="padding:8px 10px;border-radius:var(--cb-radius-md);cursor:pointer;margin-bottom:2px;transition:background var(--cb-transition-fast);display:flex;align-items:center;justify-content:space-between;" :style="{ background: activeConvId === conv.id ? 'rgba(0,82,255,.08)' : 'transparent' }" @click="selectConv(conv)">
          <div style="overflow:hidden;flex:1;"><div style="font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ conv.title }}</div><div style="font-size:10px;color:var(--cb-text-tertiary);">{{ conv.created_at?.slice(0,16) }}</div></div>
          <div style="display:flex;gap:2px;flex-shrink:0;"><button style="width:22px;height:22px;font-size:10px;border-radius:50%;display:flex;align-items:center;justify-content:center;" @click.stop="renameConv(conv)">✏</button><button style="width:22px;height:22px;font-size:10px;border-radius:50%;display:flex;align-items:center;justify-content:center;" @click.stop="removeConv(conv)">✕</button></div>
        </div>
      </div>
    </div>
    <div style="flex:1;display:flex;flex-direction:column;">
      <div v-if="activeConvId" style="padding:12px 16px;border-bottom:1px solid var(--cb-border);font-weight:600;font-size:14px;">{{ conversations.find(c => c.id === activeConvId)?.title || '' }}</div>
      <div id="chat-msgs" style="flex:1;overflow-y:auto;padding:16px;">
        <div v-if="!activeConvId" class="empty-state" style="margin-top:48px;"><div class="empty-icon" style="display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:var(--cb-blue);color:#fff;font-size:20px;font-weight:700;">Q</div><h4>AI 金融助手</h4><p class="text-sm text-muted mb-2">开始对话，获取金融分析</p><div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:center;"><button v-for="s in suggestions" :key="s" class="btn btn-ghost btn-sm" @click="useSuggestion(s)">{{ s }}</button></div></div>
        <div v-for="msg in messages" :key="msg.id" :style="{ display:'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: '12px' }">
          <div :style="{ maxWidth:'75%', padding:'10px 14px', borderRadius: 'var(--cb-radius-lg)', background: msg.role === 'user' ? 'var(--cb-blue)' : 'var(--cb-gray)', color: msg.role === 'user' ? '#fff' : 'var(--cb-text-primary)', fontSize:'14px', lineHeight:'1.5' }">
            <div v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)"></div>
            <div v-else>{{ msg.content }}</div>
            <div style="font-size:10px;margin-top:4px;opacity:.5;">{{ msg.created_at?.slice(11,16) }}</div>
          </div>
        </div>
        <div v-if="sending" style="display:flex;gap:4px;padding:8px;">
          <span style="width:6px;height:6px;border-radius:50%;background:var(--cb-text-tertiary);animation: typing 1.4s ease-in-out infinite;" />
          <span style="width:6px;height:6px;border-radius:50%;background:var(--cb-text-tertiary);animation: typing 1.4s ease-in-out .2s infinite;" />
          <span style="width:6px;height:6px;border-radius:50%;background:var(--cb-text-tertiary);animation: typing 1.4s ease-in-out .4s infinite;" />
        </div>
      </div>
      <div style="padding:12px 16px;border-top:1px solid var(--cb-border);">
        <div style="display:flex;gap:8px;"><textarea v-model="inputText" :disabled="sending" class="form-input" placeholder="输入问题..." rows="1" style="flex:1;resize:none;min-height:38px;max-height:100px;" @keydown="handleKeydown"></textarea><button class="btn btn-primary" :disabled="!inputText.trim() || sending" @click="sendMessage">发送</button></div>
        <div class="text-xs text-muted mt-1">Enter 发送</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes typing { 0%,60%,100% { transform:translateY(0); } 30% { transform:translateY(-5px); } }
@media (max-width: 640px) { .chat-sidebar-hidden { width: 100%; min-width: 100%; } }
</style>
