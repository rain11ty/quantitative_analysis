# Vue frontend bootstrap

This folder is the isolated Vue 3 frontend scaffold for the Flask project.

## Why it exists

- Keep the legacy Flask templates working while Vue pages are rebuilt in parallel.
- Reuse the existing same-origin Flask auth and `/api/*` endpoints.
- Build static assets into `app/static/vue` so Flask or Nginx can serve one site.

## Planned runtime shape

- Legacy pages stay on their current routes for now.
- New Vue pages will eventually live under `/app` during migration.
- Vue talks to Flask over same-origin `/api`, `/auth`, and `/admin` paths.

## Commands

```bash
npm install
npm run dev
npm run build
npm exec vue-tsc -- --noEmit -p tsconfig.json
```

## Notes

- `npm run dev` starts Vite on `http://127.0.0.1:5173`.
- The dev server proxies Flask requests to `http://127.0.0.1:5000`.
- `npm run build` writes production assets to `app/static/vue`.
- `npm exec vue-tsc -- --noEmit -p tsconfig.json` is the quickest sanity check for the Vue code.
- No Flask routes were switched to Vue yet in this bootstrap pass.
