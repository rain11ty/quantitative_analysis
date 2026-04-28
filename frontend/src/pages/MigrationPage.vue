<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

const title = computed(() => String(route.meta.title || 'Migration Page'));
const summary = computed(() => String(route.meta.summary || '该页面正在从 Flask 模板迁移到 Vue 组件。'));
const legacyTemplate = computed(() => String(route.meta.legacyTemplate || ''));
const priority = computed(() => String(route.meta.priority || 'Planned'));
const apiGroups = computed(() => {
  const value = route.meta.apiGroups;
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
});

const priorityTone = computed(() => {
  const p = priority.value.toLowerCase();
  if (p.includes('phase 1')) return 'info';
  if (p.includes('phase 2')) return 'warning';
  return 'neutral';
});
</script>

<template>
  <section style="display:flex;flex-direction:column;gap:1rem;">
    <div class="card">
      <div class="card-body">
        <div class="flex-between">
          <div>
            <p class="text-xs text-muted" style="text-transform:uppercase;letter-spacing:.05em;">Migration Target</p>
            <h3>{{ title }}</h3>
          </div>
          <span class="badge" :class="'badge-' + priorityTone">{{ priority }}</span>
        </div>
        <p class="text-sm text-muted mt-2">{{ summary }}</p>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header"><h3>Legacy 模板</h3></div>
        <div class="card-body">
          <p class="font-mono text-sm" style="word-break:break-all;">{{ legacyTemplate || '未指定' }}</p>
          <p class="text-xs text-muted mt-2">旧版 Flask 模板保留为实时参考，直到 Vue 路由完成重构。</p>
        </div>
      </div>

      <div class="card">
        <div class="card-header"><h3>路由参数</h3></div>
        <div class="card-body">
          <pre class="font-mono text-sm" style="background:var(--color-surface-hover);padding:.75rem;border-radius:var(--radius-sm);overflow-x:auto;">{{ JSON.stringify(route.params, null, 2) }}</pre>
        </div>
      </div>
    </div>

    <div v-if="apiGroups.length" class="card">
      <div class="card-header"><h3>API 接口组</h3></div>
      <div class="card-body">
        <div style="display:flex;flex-wrap:wrap;gap:.5rem;">
          <span v-for="g in apiGroups" :key="g" class="badge badge-neutral">{{ g }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
