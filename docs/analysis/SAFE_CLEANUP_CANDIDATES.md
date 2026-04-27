# Safe Cleanup Candidates

Updated: `2026-04-28`

## Already cleaned in code

- `app/api/__init__.py`
  Removed duplicate `news_api` import and made blueprint side-effect imports explicit.
- `app/main/__init__.py`
  Marked `views` import as intentional side-effect import.
- `app/main/views.py`
  Removed unused `request` and `StockService` imports.
- `app/api/news_api.py`
  Removed unused `hashlib` import.
- `app/extensions.py`
  Removed unused `smtplib` import inside `init_mail()`.
- `app/models/stock_business.py`
  Removed unused `datetime` import.
- `app/models/stock_minute_data.py`
  Removed unused `datetime` import.

## High-confidence orphan files

These are not part of the active Flask route/template chain and can be removed or archived with low risk.

- `app/templates/analysis.html`
  The `/analysis` route now redirects to `/stocks`, and `stock_detail.html` already contains the merged technical analysis UI.
- `app/static/css/mobile.css`
  No template or Python file references this stylesheet. Active layout uses `financial-theme.css`, `responsive-financial.css`, and `js/mobile.js`.

## Reserved or legacy modules

These are not dead by definition, but they are not part of the active runtime path today. Archive them only if you are sure you do not want to keep the reserved implementation.

- `app/services/backtest_engine.py`
  Reserved advanced backtest engine. Current live backtest logic is implemented inside `app/api/analysis_api.py`.
  Note: this file currently has broken references to `db` if someone tries to enable it directly.
- `app/celery_app.py`
  Reserved Celery configuration.
- `app/tasks.py`
  Reserved Celery task definitions.
- `.codebuddy/fix_template_encoding.py`
  Dev helper script, not used by runtime.

## Local generated artifacts

These are not tracked by Git and are safe to delete when you no longer need the local data.

- `.venv/`
- `node_modules/`
- `__pycache__/`
- `logs/`
- `stock_analysis.db`
- `_dump_docker_empty.sql`
- `_local_data_dump.sql`

## Docs or launcher drift

These are not cleanup targets by themselves, but they should be updated if you continue maintaining the repo.

- `run_system.py`
  Mentions `docs/archive` and `images/`; `docs/archive` exists, but `images/` does not.
- `docs/guides/CURRENT_WORKSPACE_STRUCTURE.md`
  Still describes `analysis.html` as remaining in templates even though the active UI has already moved into `stock_detail.html`.

## Verified active files

These looked suspicious at first glance but are still in active use and should not be removed.

- `app/templates/auth/profile.html`
- `app/templates/admin/logs.html`
- `app/templates/admin/user_detail.html`
- `start-docker.bat`
- `stop-docker.bat`
- `quick_start.py`
- `run_system.py`
