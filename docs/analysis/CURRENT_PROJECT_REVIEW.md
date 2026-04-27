# Current Project Review

> Snapshot date: `2026-04-28`

## Overall assessment

The current repository is a usable Flask-based A-share analysis system, not a half-finished prototype. The main user-facing path already covers market overview, stock lookup, stock detail analysis, screening, backtesting, realtime monitor, AI assistant, authentication, and an admin console.

Compared with the older `ml_factor` branch-style materials, the active system has clearly converged on a server-rendered Flask application with Jinja2 templates plus JSON APIs.

## What is in good shape

- The runtime entry path is clear: `run.py` / `quick_start.py` / `run_system.py` all end at `app.create_app()`.
- The application layering is readable: `main` for pages, `api` for JSON, `routes` for auth/admin, `services` for business logic, `models` for ORM.
- User data features are more complete than older docs suggested:
  - watchlist supports create/read/update/delete
  - analysis records support create/read/update/delete
  - backtest results are persisted for logged-in users
  - admin user list already has pagination
- Realtime and market overview modules include graceful degradation paths instead of hard-failing on one upstream source.
- AI conversation storage has a structured table design and supports SSE streaming replies.

## Main risks that still matter

### 1. No real automated test suite

The repo still does not contain a project-owned `tests/` directory. Diagnostics scripts exist, but they are manual smoke checks rather than regression protection.

### 2. Documentation had drifted away from the code

Several documents were still describing:

- `22` ORM models, while the current code exports `24`
- an unfinished admin pagination state that has already been implemented
- financial data sync flows that are not actually wired into `scripts/sync_tushare_data.py`

This review is being kept intentionally short because the wider `docs/` set has now been realigned to the codebase.

### 3. Legacy and active data paths coexist

- AI messages are stored in the new conversation tables, but successful replies may still be mirrored into `user_chat_history`.
- `app/services/backtest_engine.py` is an advanced reserved implementation, while the currently active backtest logic lives inside `app/api/analysis_api.py`.
- Financial statement scripts under `app/utils/` are standalone legacy sync scripts, not part of the main web request path.

### 4. Removed `ml_factor` materials no longer belong to the active product

The empty archived markdown files under `docs/archive/ml_factor/` were not carrying useful information anymore and should not be treated as part of the current product documentation set.

## Recommended next steps

1. Add a small `pytest` suite for `stock_api`, `analysis_api`, and the auth/admin guards.
2. Decide whether to keep `user_chat_history` as a compatibility table or retire it after profile/admin pages migrate.
3. Move the active backtest implementation to one shared service to remove the split between `analysis_api.py` and `backtest_engine.py`.
4. If financial statements will remain in scope, promote those standalone scripts into supported `scripts/` commands or service-layer jobs.
