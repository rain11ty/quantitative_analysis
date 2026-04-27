<script setup lang="ts">
const priorities = [
  {
    title: 'Phase 1',
    pages: ['Stock Detail', 'Realtime Monitor', 'AI Assistant'],
    reason: 'Stock Detail is already the first implemented Vue page; the rest of phase 1 should now reuse its patterns.',
  },
  {
    title: 'Phase 2',
    pages: ['Stocks', 'Screen', 'Backtest'],
    reason: 'These can reuse the shared shell, request helpers, and chart wrappers from Phase 1.',
  },
  {
    title: 'Phase 3',
    pages: ['News', 'Auth polish', 'Admin review'],
    reason: 'Finish lower-risk views after the main trading workflows are stable.',
  },
];

const safeguards = [
  'Keep legacy Flask routes and templates live until each Vue page passes side-by-side review.',
  'Reuse same-origin Session and Cookie auth instead of introducing cross-origin complexity.',
  'Ship Vue pages behind /app first, then cut over route by route after acceptance.',
  'Use the new stock detail page as the reference implementation for charts, tab loading, and auth-aware actions.',
];
</script>

<template>
  <section class="panel stack">
    <div class="hero-card">
      <p class="eyebrow">Migration strategy</p>
      <h3>Independent frontend, same deployment</h3>
      <p>
        This workspace is set up for a gradual Vue migration. The current Flask
        templates stay available while new pages are rebuilt, reviewed, and
        rolled out under a separate route prefix.
      </p>
    </div>

    <div class="grid two-column">
      <article class="panel-card">
        <h4>Delivery order</h4>
        <div class="phase-list">
          <section v-for="priority in priorities" :key="priority.title">
            <p class="phase-title">{{ priority.title }}</p>
            <p>{{ priority.pages.join(' / ') }}</p>
            <p class="muted">{{ priority.reason }}</p>
          </section>
        </div>
      </article>

      <article class="panel-card">
        <h4>Safety rails</h4>
        <ul class="plain-list">
          <li v-for="item in safeguards" :key="item">{{ item }}</li>
        </ul>
      </article>
    </div>
  </section>
</template>
