<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
const route = useRoute();
const title = computed(() => String(route.meta.title || 'Migration'));
const legacyTemplate = computed(() => String(route.meta.legacyTemplate || '未指定'));
const priority = computed(() => String(route.meta.priority || 'Planned'));
const apiGroups = computed(() => { const v = route.meta.apiGroups; return Array.isArray(v) ? v.map(i => String(i)) : []; });
</script>

<template>
  <div>
    <div class="card">
      <div class="card-header"><h3>{{ title }}</h3><span class="badge badge-neutral">{{ priority }}</span></div>
      <p class="text-sm text-muted">该页面正在从 Flask 模板迁移到 Vue 组件。</p>
    </div>
    <div class="grid-2">
      <div class="card"><div class="card-header"><h3>Legacy 模板</h3></div><p class="font-mono text-sm" style="word-break:break-all;">{{ legacyTemplate }}</p></div>
      <div class="card"><div class="card-header"><h3>路由参数</h3></div><pre class="font-mono text-xs" style="background:var(--cb-gray);padding:12px;border-radius:var(--cb-radius-sm);overflow-x:auto;">{{ JSON.stringify(route.params, null, 2) }}</pre></div>
    </div>
    <div v-if="apiGroups.length" class="card">
      <div class="card-header"><h3>API 接口组</h3></div>
      <div class="flex-between gap-1" style="flex-wrap:wrap;"><span v-for="g in apiGroups" :key="g" class="badge badge-neutral">{{ g }}</span></div>
    </div>
  </div>
</template>
