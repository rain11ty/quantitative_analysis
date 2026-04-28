<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { useToast } from '../composables/useToast';
import {
  getConversations, createConversation, getMessages, renameConversation,
  deleteConversation, sendChatMessage, type Conversation, type ChatMessage,
} from '../modules/ai-assistant/api';

const toast = useToast();

const conversations = ref<Conversation[]>([]);
const activeConvId = ref<number | null>(null);
const messages = ref<ChatMessage[]>([]);
const inputText = ref('');
const loading = ref(false);
const sending = ref(false);
const convSearch = ref('');
const streamingContent = ref('');

const filteredConversations = computed(() => {
  if (!convSearch.value) return conversations.value;
  const q = convSearch.value.toLowerCase();
  return conversations.value.filter((c) => c.title?.toLowerCase().includes(q));
});

onMounted(async () => {
  try {
    const res = await getConversations();
    conversations.value = res.data || [];
    if (conversations.value.length > 0) {
      activeConvId.value = conversations.value[0].id;
      await loadMessages(activeConvId.value);
    }
  } catch {
    toast.error('对话列表加载失败');
  }
});

async function loadMessages(convId: number) {
  try {
    const res = await getMessages(convId);
    messages.value = res.data || [];
    await nextTick();
    scrollBottom();
  } catch {
    toast.error('消息加载失败');
  }
}

async function selectConv(conv: Conversation) {
  activeConvId.value = conv.id;
  await loadMessages(conv.id);
}

async function newConv() {
  try {
    const title = '新的对话';
    const res = await createConversation(title);
    const c = res.data;
    conversations.value.unshift(c);
    activeConvId.value = c.id;
    messages.value = [];
  } catch {
    toast.error('创建对话失败');
  }
}

async function sendMessage() {
  const text = inputText.value.trim();
  if (!text || sending.value) return;
  if (!activeConvId.value) await newConv();
  if (!activeConvId.value) return;

  const convId = activeConvId.value;
  const userMsg: ChatMessage = { id: Date.now(), role: 'user', content: text, created_at: new Date().toISOString() };
  messages.value.push(userMsg);
  inputText.value = '';
  sending.value = true;
  streamingContent.value = '';

  await nextTick();
  scrollBottom();

  try {
    const response = await sendChatMessage(convId, text);

    if (response.ok && response.headers.get('content-type')?.includes('text/event-stream')) {
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      const assistantMsg: ChatMessage = { id: Date.now() + 1, role: 'assistant', content: '', created_at: new Date().toISOString() };
      messages.value.push(assistantMsg);
      let buffer = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              try {
                const parsed = JSON.parse(data);
                assistantMsg.content += parsed.content || parsed.message || parsed.delta || '';
                streamingContent.value = assistantMsg.content;
              } catch { assistantMsg.content += data; }
              await nextTick();
              scrollBottom();
            }
          }
        }
      }
    } else {
      const data = await response.json();
      const reply = data.data?.reply || data.message || JSON.stringify(data);
      messages.value.push({ id: Date.now() + 1, role: 'assistant', content: reply, created_at: new Date().toISOString() });
    }
  } catch {
    messages.value.push({ id: Date.now() + 1, role: 'assistant', content: '抱歉，请求失败，请重试。', created_at: new Date().toISOString() });
    toast.error('消息发送失败');
  }

  sending.value = false;
  streamingContent.value = '';
  await nextTick();
  scrollBottom();

  // Refresh conversation list to update title
  try {
    const res = await getConversations();
    conversations.value = res.data || [];
  } catch { /* */ }
}

async function renameConv(conv: Conversation) {
  const title = prompt('新标题:', conv.title);
  if (title && title !== conv.title) {
    try {
      await renameConversation(conv.id, title);
      conv.title = title;
    } catch { toast.error('重命名失败'); }
  }
}

async function removeConv(conv: Conversation) {
  if (!confirm('确定删除此对话？')) return;
  try {
    await deleteConversation(conv.id);
    conversations.value = conversations.value.filter((c) => c.id !== conv.id);
    if (activeConvId.value === conv.id) {
      activeConvId.value = conversations.value[0]?.id || null;
      if (activeConvId.value) await loadMessages(activeConvId.value);
      else messages.value = [];
    }
    toast.success('对话已删除');
  } catch { toast.error('删除失败'); }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function scrollBottom() {
  const el = document.getElementById('chat-messages');
  if (el) el.scrollTop = el.scrollHeight;
}

function renderMarkdown(text: string): string {
  return text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/\n/g, '<br>');
}

const suggestions = [
  '分析一下上证指数的走势', '最近哪个行业最强势？',
  '推荐几只值得关注的股票', '什么是MACD金叉死叉？',
  '今天市场有什么重要消息？', '如何构建量化选股策略？',
];

function useSuggestion(s: string) { inputText.value = s; sendMessage(); }

const activeConv = computed(() => conversations.value.find((c) => c.id === activeConvId.value));
</script>

<template>
  <div class="chat-layout">
    <!-- Sidebar -->
    <div class="chat-sidebar">
      <div class="chat-sidebar-header">
        <button class="btn btn-primary w-full btn-sm" @click="newConv">+ 新对话</button>
      </div>
      <div class="chat-sidebar-search">
        <input v-model="convSearch" class="form-input" placeholder="搜索对话..." />
      </div>
      <div class="chat-sidebar-list">
        <div v-if="filteredConversations.length === 0" class="text-xs text-muted" style="text-align:center;padding:1rem;">暂无对话</div>
        <div
          v-for="conv in filteredConversations" :key="conv.id"
          class="conv-item"
          :class="{ active: activeConvId === conv.id }"
          @click="selectConv(conv)"
        >
          <div class="conv-info">
            <div class="conv-title">{{ conv.title }}</div>
            <div class="conv-meta">{{ conv.created_at?.slice(0, 16) }}</div>
          </div>
          <div class="conv-actions">
            <button class="btn-icon btn-ghost" style="width:24px;height:24px;font-size:.7rem;" @click.stop="renameConv(conv)" title="重命名">✏</button>
            <button class="btn-icon btn-ghost" style="width:24px;height:24px;font-size:.7rem;" @click.stop="removeConv(conv)" title="删除">✕</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Chat Panel -->
    <div class="chat-panel">
      <!-- Header -->
      <div v-if="activeConv" class="card-header chat-header">
        <h3>{{ activeConv.title }}</h3>
        <span v-if="activeConv.message_count" class="badge badge-neutral">{{ activeConv.message_count }} 条消息</span>
      </div>

      <!-- Messages -->
      <div id="chat-messages" class="chat-messages">
        <div v-if="!activeConvId" class="empty-state" style="margin-top:4rem;">
          <div class="empty-icon">🤖</div>
          <h4>AI 金融助手</h4>
          <p class="text-sm text-muted mb-3">开始新对话，获取金融分析和投资建议</p>
          <div class="suggestion-grid">
            <button v-for="s in suggestions" :key="s" class="btn btn-sm btn-outline" @click="useSuggestion(s)">{{ s }}</button>
          </div>
        </div>

        <div v-for="msg in messages" :key="msg.id" class="msg-row" :class="'msg-' + msg.role">
          <div class="msg-bubble">
            <div v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)" class="msg-content"></div>
            <div v-else class="msg-content">{{ msg.content }}</div>
            <div class="msg-time">{{ msg.created_at?.slice(11, 16) }}</div>
          </div>
        </div>

        <div v-if="sending" class="msg-row msg-assistant">
          <div class="msg-bubble">
            <div class="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- Composer -->
      <div class="chat-composer">
        <div class="composer-inner">
          <textarea
            v-model="inputText" :disabled="sending" class="form-input composer-input"
            placeholder="输入问题，Enter 发送..."
            rows="1" @keydown="handleKeydown"
          ></textarea>
          <button class="btn btn-primary" :disabled="!inputText.trim() || sending" @click="sendMessage">发送</button>
        </div>
        <div class="text-xs text-muted mt-1">Enter 发送 · Shift+Enter 换行</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-layout {
  display:flex; gap:0; height:calc(100vh - 120px);
}

.chat-sidebar {
  width:260px; min-width:260px;
  border-right:1px solid var(--color-border);
  background:var(--color-surface);
  display:flex; flex-direction:column;
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
}
.chat-sidebar-header { padding:.75rem; }
.chat-sidebar-search { padding:0 .75rem .5rem; }
.chat-sidebar-search .form-input { font-size:.8rem; }
.chat-sidebar-list {
  flex:1; overflow-y:auto; padding:0 .5rem;
}

.conv-item {
  padding:.5rem .65rem; border-radius:var(--radius-md);
  cursor:pointer; margin-bottom:.2rem;
  transition:background var(--transition);
  display:flex; align-items:center; justify-content:space-between;
}
.conv-item:hover { background: var(--color-surface-hover); }
.conv-item.active { background: rgba(26,115,232,.1); }
.conv-info { overflow:hidden; flex:1; min-width:0; }
.conv-title { font-size:.82rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:500; }
.conv-meta { font-size:.7rem; color:var(--color-text-muted); }
.conv-actions { display:flex; gap:.2rem; flex-shrink:0; }

.chat-panel {
  flex:1; display:flex; flex-direction:column;
  background: var(--color-surface);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
}
.chat-header { border-bottom:1px solid var(--color-border); }

.chat-messages { flex:1; overflow-y:auto; padding:1rem; }

.msg-row { display:flex; margin-bottom:.75rem; }
.msg-user { justify-content:flex-end; }
.msg-assistant { justify-content:flex-start; }

.msg-bubble {
  max-width:75%; padding:.65rem 1rem; border-radius:var(--radius-lg);
  line-height:1.55;
}
.msg-user .msg-bubble { background:var(--color-primary); color:#fff; }
.msg-assistant .msg-bubble { background:var(--color-bg); color:var(--color-text); border:1px solid var(--color-border); }

.msg-content { font-size:.88rem; }
.msg-content :deep(.code-block) {
  background:#1e1e2e; color:#cdd6f4; padding:.75rem; border-radius:var(--radius-sm);
  font-size:.78rem; overflow-x:auto; margin:.5rem 0;
}
.msg-content :deep(.inline-code) {
  background:rgba(0,0,0,.06); padding:1px 6px; border-radius:4px;
  font-size:.82rem; font-family:var(--font-mono);
}
.msg-user .msg-content :deep(.inline-code) { background:rgba(255,255,255,.15); }
.msg-time { font-size:.68rem; margin-top:.25rem; opacity:.6; }

.suggestion-grid {
  display:flex; flex-wrap:wrap; gap:.5rem; justify-content:center;
}

.typing-indicator {
  display:flex; gap:4px; padding:.25rem 0;
}
.typing-indicator span {
  width:7px; height:7px; border-radius:50%; background:var(--color-text-muted);
  animation: typing-bounce 1.4s ease-in-out infinite;
}
.typing-indicator span:nth-child(2) { animation-delay:.2s; }
.typing-indicator span:nth-child(3) { animation-delay:.4s; }
@keyframes typing-bounce {
  0%,60%,100% { transform:translateY(0); }
  30% { transform:translateY(-4px); }
}

.chat-composer {
  padding:.75rem 1rem; border-top:1px solid var(--color-border);
  background:var(--color-surface);
}
.composer-inner { display:flex; gap:.5rem; }
.composer-input { flex:1; resize:none; min-height:44px; max-height:120px; }

@media (max-width: 768px) {
  .chat-layout { flex-direction:column; height:calc(100vh - 100px); }
  .chat-sidebar { width:100%; min-width:100%; max-height:200px; border-radius:var(--radius-lg) var(--radius-lg) 0 0; }
  .chat-panel { border-radius:0 0 var(--radius-lg) var(--radius-lg); }
}
</style>
