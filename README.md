# FarmLink

FarmLink is an SIH26033 marketplace prototype that connects local farmers and FPOs directly with consumers and bulk buyers. It includes JWT role authentication, produce listings, freshness calculations, order requests, seeded demo accounts, and a PostgreSQL-ready backend.

## Quick start

1. Install frontend dependencies with `pnpm install` in `frontend`.
2. Create a Python environment and install `backend/requirements.txt`.
3. Start PostgreSQL with `docker compose up -d db`, then copy `backend/.env.example` to `backend/.env`.
4. From `backend`, run `uvicorn app.main:app --reload`.
5. From `frontend`, run `pnpm dev`.

For a zero-configuration local preview, omit `DATABASE_URL`; the backend uses SQLite and seeds demo data automatically. For PostgreSQL, set `DATABASE_URL=postgresql+psycopg://farmlink:farmlink@localhost:5432/farmlink`.

## Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Buyer | buyer@farmlink.demo | Demo123! |
| Farmer | farmer@farmlink.demo | Demo123! |
| Admin | admin@farmlink.demo | Demo123! |

## Current MVP scope

The implemented demo covers direct marketplace discovery, calculated freshness states, buyer orders, JWT-based role checks, farmer listing creation API, and recommendations seeded from live marketplace data. Trading, subscriptions, demand forecasting, maps, full profile editing, and admin moderation are defined by the specification as the next backend phases.
