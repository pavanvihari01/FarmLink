# FarmLink

FarmLink is an SIH26033 marketplace prototype that connects local farmers and FPOs directly with consumers and bulk buyers. It includes JWT role authentication, produce listings, freshness calculations, order requests, seeded demo accounts, Alembic migrations, and a PostgreSQL-primary backend with a zero-config SQLite fallback.

## Quick start

### Option A — SQLite (zero config)

1. Install frontend dependencies with `pnpm install` in `frontend`.
2. Create a Python environment and install `backend/requirements.txt`.
3. From `backend`, run `uvicorn app.main:app --reload`.

Leave `DATABASE_URL` unset. The backend creates `backend/farmlink.db`, runs `create_all()`, and seeds demo data because `DEMO_MODE` defaults to `true`.

### Option B — PostgreSQL (primary path)

1. Install frontend dependencies with `pnpm install` in `frontend`.
2. Create a Python environment and install `backend/requirements.txt`.
3. Start PostgreSQL with `docker compose up -d db`.
4. Copy `backend/.env.example` to `backend/.env` and confirm `DATABASE_URL` points at the compose service.
5. From `backend`, apply migrations: `alembic upgrade head`.
6. From `backend`, run `uvicorn app.main:app --reload`.

PostgreSQL never calls `create_all()`. The schema is owned by Alembic; if you skip step 5, the API will start but every query will fail against missing tables.

### Frontend

From `frontend`, run `pnpm dev`.

## Database

`DATABASE_URL` is the single source of truth and is read from `backend/.env` or the process environment.

- **Unset** → `sqlite:///backend/farmlink.db`, absolute path, independent of the shell's working directory.
- **Set** → that URL is used verbatim.

For PostgreSQL:

```

DATABASE_URL=postgresql+psycopg://farmlink:farmlink@localhost:5432/farmlink

```

### Migrations

Run Alembic from `backend/`:

```

alembic upgrade head                        # apply all migrations
alembic revision --autogenerate -m "..."    # generate a new migration
alembic downgrade -1                        # revert the last migration

```

If you have an existing SQLite dev database that predates Alembic, mark it as current instead of replaying the initial migration:

```

alembic stamp head

```

### Demo seeding

`seed()` runs only when `DEMO_MODE=true` (the default) and only on an empty database. Set `DEMO_MODE=false` when pointing at a real PostgreSQL instance to keep it clean.

## Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Buyer | buyer@farmlink.demo | Demo123! |
| Farmer | farmer@farmlink.demo | Demo123! |
| Admin | admin@farmlink.demo | Demo123! |

The seed also creates `fpo@farmlink.demo` (farmer) and `bulk@farmlink.demo` (buyer) for the bulk-buyer flow.

## Current MVP scope

The implemented demo covers direct marketplace discovery, calculated freshness states, buyer orders, JWT-based role checks, farmer listing creation API, and recommendations seeded from live marketplace data. Trading, subscriptions, demand forecasting, maps, full profile editing, and admin moderation are defined by the specification as the next backend phases.
