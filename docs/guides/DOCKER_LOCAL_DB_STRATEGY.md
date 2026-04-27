# Docker and Local Database Strategy

## The root issue

This project can easily end up using two different MySQL databases:

- Local Flask usually reads `.env` and defaults to `localhost:3306`.
- Docker Flask connects to the Docker MySQL service on `mysql:3306`.
- From the host machine, that same Docker MySQL is exposed as `127.0.0.1:3307`.

If local Flask uses host MySQL while Docker uses container MySQL, then user data, watchlists, AI conversations, and backtest results will drift apart.

## Recommended approach

Use one database as the single source of truth during development.

If your host MySQL currently has the fresher and more complete data, keep it as the source of truth for now instead of trying to use the stale Docker MySQL copy.

That means:

- local Flask should keep using host MySQL
- Docker Flask should also point to that same host MySQL
- the Docker MySQL service should be treated as stale until you intentionally refresh it

## Option A: Docker MySQL is the source of truth

The simplest choice for this repository is:

- run MySQL in Docker
- let Docker Flask connect to `mysql:3306`
- let local Flask connect to `127.0.0.1:3307`

That way local development and Docker development see the same data.

## Local `.env` example for sharing Docker MySQL

```env
DB_HOST=127.0.0.1
DB_PORT=3307
DB_USER=root
DB_PASSWORD=123456
DB_NAME=stock_cursor

REDIS_HOST=127.0.0.1
REDIS_PORT=6380
REDIS_DB=0
```

Notes:

- `DB_PORT=3307` is the host-side port published by `docker-compose.dev.yml` and `docker-compose.yml`.
- `REDIS_PORT=6380` is the host-side Redis port published by Docker.
- Inside Docker, services still use `DB_HOST=mysql` and the default MySQL port `3306`.

## Option B: host MySQL is the source of truth

Choose this when your host MySQL is more complete than the Docker copy.

### Local Flask

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_real_password
DB_NAME=stock_cursor
```

### Docker Flask

Use environment like this for the `web` service:

```env
DOCKER_DB_HOST=host.docker.internal
DOCKER_DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_real_password
DB_NAME=stock_cursor
```

On Windows with Docker Desktop, `host.docker.internal` is usually the cleanest way for the container to reach services running on the host.

The repository compose files now support these dedicated variables, so local Flask can keep using `DB_HOST/DB_PORT` while Docker Flask separately uses `DOCKER_DB_HOST/DOCKER_DB_PORT`.

## What changed in code

`config.py` now supports a dedicated `DB_PORT` environment variable.

It is also backward-compatible with older `.env` styles where `DB_HOST` already contains a port, such as `127.0.0.1:3307`.

## Practical rule

Pick one of these two patterns and stay consistent:

1. Local Flask and Docker Flask both use Docker MySQL.
2. Local Flask and Docker Flask both use your host MySQL.

Do not mix them during feature work unless you intentionally want separate datasets.
