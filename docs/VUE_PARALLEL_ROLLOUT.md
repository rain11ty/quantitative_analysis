# Vue parallel rollout

This document turns the migration idea into a safe execution path for this repository.

## Goals

- Keep the current Flask application usable during the migration.
- Move the frontend to Vue 3 without rewriting the Flask business layer.
- Deploy frontend and backend together under the same site and auth model.

## Current branch strategy

- Stable base branch stays untouched.
- Vue work happens on `codex-vue-refactor`.
- Existing template routes remain the live product until route-by-route acceptance.

## What was added in this bootstrap pass

- A new `frontend/` Vue 3 + Vite + TypeScript scaffold.
- Same-origin proxy and build settings for Flask integration.
- Placeholder Vue routes under the planned `/app` namespace.
- A scoped Flask `/app` shell route and Vite asset loader.
- No legacy Flask route was replaced.

## Current implementation status

- `frontend/src/pages/StockDetailPage.vue` now contains the first real Vue migration target.
- The Vue stock detail page includes:
  - stock summary and valuation cards
  - realtime quote + K-line chart
  - history tab with presets, date filtering, and load-more behavior
  - technical analysis tab with lazy loading, indicator switching, and silent analysis-record save
  - moneyflow and chip-distribution tabs with charts and tables
- Legacy `/stock/<ts_code>` remains untouched. The new page is intended for `/app/stock/<tsCode>` once frontend assets are served.

## Runtime target

During migration:

- Legacy routes keep serving Jinja templates.
- New Vue pages are introduced under `/app`.
- Vue requests existing Flask endpoints over `/api`, `/auth`, and `/admin`.

After acceptance:

- We can cut over one page at a time from legacy routes to Vue routes.
- Legacy templates are removed only after page parity is verified.

## Why `/app` is the safest first rollout

- It avoids breaking bookmarks for current template pages.
- It allows side-by-side comparison between legacy and Vue flows.
- It preserves the current Flask session and cookie behavior.
- It gives us one place to wire SPA fallback later.

## Proposed milestones

1. Bootstrap the Vue app and shared frontend primitives.
2. Implement `stock_detail` in Vue and compare it against the legacy page.
3. Implement `realtime_monitor` and standardize polling and chart cleanup.
4. Implement `ai_assistant` with conversation and streaming state management.
5. Reuse the shared shell for `stocks`, `screen`, `backtest`, and `news`.
6. Implement the first real Vue page behind the existing `/app` shell.
7. Cut over route by route after acceptance and only then delete legacy templates.

## Acceptance checklist per page

- Feature parity with the legacy page.
- Login and logout behavior unchanged.
- API payloads unchanged unless intentionally versioned.
- Mobile layout still usable.
- Old page still available until sign-off.

## Next backend changes

These are the next backend changes I plan to make after the first real Vue page exists:

- Pass richer page-specific bootstrap data into the Vue shell where needed.
- Add deployment wiring if Nginx needs explicit cache rules for `app/static/vue`.
- Introduce route-by-route redirects only after parity checks pass.
