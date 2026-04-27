<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

const title = computed(() => String(route.meta.title || 'Migration Page'));
const summary = computed(() => String(route.meta.summary || ''));
const legacyTemplate = computed(() => String(route.meta.legacyTemplate || ''));
const priority = computed(() => String(route.meta.priority || 'Planned'));
const apiGroups = computed(() => {
  const value = route.meta.apiGroups;
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
});
const routeParams = computed(() => route.params);
</script>

<template>
  <section class="stack">
    <article class="panel-card accent-card">
      <div class="page-header-row">
        <div>
          <p class="eyebrow">Migration target</p>
          <h3>{{ title }}</h3>
        </div>
        <span class="status-pill">{{ priority }}</span>
      </div>
      <p>{{ summary }}</p>
    </article>

    <div class="grid two-column">
      <article class="panel-card">
        <h4>Legacy source</h4>
        <p class="path-label">{{ legacyTemplate }}</p>
        <p class="muted">
          The old Flask template remains the live reference until this route is
          rebuilt and accepted.
        </p>
      </article>

      <article class="panel-card">
        <h4>Route context</h4>
        <pre class="code-block">{{ JSON.stringify(routeParams, null, 2) }}</pre>
      </article>
    </div>

    <article class="panel-card">
      <h4>API groups to preserve</h4>
      <ul class="plain-list">
        <li v-for="apiGroup in apiGroups" :key="apiGroup">{{ apiGroup }}</li>
      </ul>
    </article>
  </section>
</template>
