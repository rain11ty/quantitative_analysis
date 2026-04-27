# Safe Web-Only Deployment

Use this checklist when you want to ship new application code without touching the production MySQL or Redis data.

## Goal

This flow is for deployments that:

- update Flask or frontend code
- rebuild only the `web` service
- keep the existing `mysql` and `redis` containers and volumes intact
- do not run schema migrations or import SQL dumps

If a release needs database changes, stop and use a separate reviewed migration plan instead of this document.

## Core rule

Treat the database and cache as out of scope.

Only rebuild and restart `web`.

## Pre-deploy checks

Run these from the repository root on the server:

```bash
pwd
git status --short
git branch --show-current
docker compose ps
```

Confirm:

- you are in the correct repository directory
- there are no accidental edits in `.env` or deployment files
- `mysql` and `redis` are already healthy before the release starts

## Standard deployment

### 1. Fetch the target code

```bash
git fetch --all --prune
git checkout <target-branch-or-commit>
git pull --ff-only
```

If you deploy by commit SHA:

```bash
git fetch origin
git checkout <commit-sha>
```

### 2. Build frontend assets

```bash
cd frontend
npm ci
npm run build
cd ..
```

This writes the production assets into `app/static/vue` and does not touch MySQL.

### 3. Rebuild only the web service

```bash
docker compose build web
docker compose up -d --no-deps web
```

Why this is safe:

- `web` is rebuilt from the latest code
- `--no-deps` avoids restarting `mysql` and `redis`
- existing database volumes remain attached and untouched

## Post-deploy validation

### 1. Check container status

```bash
docker compose ps
curl -I http://127.0.0.1:5001/healthz
```

### 2. Inspect recent web logs

```bash
docker compose logs --tail=100 web
```

Watch for:

- Flask or Gunicorn startup failures
- import errors
- template or static asset path errors
- unexpected database migration or table creation logs

### 3. Smoke test the app

```bash
curl http://127.0.0.1:5001/app
curl http://127.0.0.1:5001/app/screen
curl http://127.0.0.1:5001/api/industries
curl http://127.0.0.1:5001/api/areas
```

Manual browser checks:

- `/app` opens correctly
- `/app/screen` loads static assets correctly
- signed-out users see a clear sign-in requirement for restricted endpoints
- signed-in users can run the screen page successfully

## Commands that are not allowed in this flow

Do not run any of the following during a web-only deployment:

```bash
docker compose down -v
docker compose up -d --build
docker compose rm -f mysql redis
docker volume rm <volume-name>
flask db upgrade
flask db migrate
mysql -u ... < some_dump.sql
mysqldump ...
```

Why they are blocked:

- they can recreate dependency services
- they can delete or replace persistent data
- they can change schema or overwrite production state

## Rollback

If only the web release is bad, roll back with the previous stable code and repeat the same web-only process:

```bash
git checkout <previous-stable-commit>
cd frontend
npm ci
npm run build
cd ..
docker compose build web
docker compose up -d --no-deps web
```

Rollback rules are the same:

- do not restart `mysql`
- do not restart `redis`
- do not import or export SQL

## Short release statement

Before each production release, confirm this sentence:

> This deployment updates only web code and static assets. It does not rebuild MySQL or Redis, delete volumes, or run database migrations.
