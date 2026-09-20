# Dispatch #4 — Order lifecycle

## What this archive contains

    FarmLink/backend/app/api/routes.py                            (order endpoints rewritten)
    FarmLink/backend/app/models/entities.py                       (one column added)
    FarmLink/backend/app/schemas/api.py                           (one schema added)
    FarmLink/backend/app/core/config.py                           (one setting added)
    FarmLink/backend/migrations/versions/0002_order_status_changed_at.py  (new)
    FarmLink/backend/tests/conftest.py                            (new)
    FarmLink/backend/tests/test_orders.py                         (new)
    FarmLink/backend/.env.example                                 (one var added)

Backend only. No frontend change — the order UIs are dispatches #5 and #6.

## How to apply

Unzip at the project root, then:

    cd E:\myApps\Project\FarmLink\backend
    pip install -r requirements.txt

**If you are on SQLite** (no `.env`): nothing else needed. `create_all()` runs
on startup and adds the new column.

**If you are on PostgreSQL**: apply the migration before starting the server.

    cd E:\myApps\Project\FarmLink
    docker compose up -d db
    cd backend
    alembic upgrade head

Then run the tests:

    pytest

Expect the two existing freshness tests plus 19 new order tests to pass.

## The bug this fixes

`POST /orders` checked `data.quantity > x.available_quantity` but never
decremented it. The same 35 kg could be ordered an unlimited number of times.
Every test in `test_orders.py` that asserts on `available_quantity` would have
failed before this dispatch.

## Stock reservation

Stock moves at four points now:

| Event | `available_quantity` |
| --- | --- |
| Order created | decreases by `quantity` |
| Order rejected | increases by `quantity` |
| Order cancelled | increases by `quantity` |
| Order completed | unchanged — produce already left the farm |

Reservation happens at creation, so a buyer cannot oversell a listing by
racing another buyer.

## Transitions

    ALLOWED_TRANSITIONS = {
        'requested': {'accepted', 'rejected', 'cancelled'},
        'accepted':  {'completed', 'cancelled'},
        'rejected':  set(),
        'cancelled': set(),
        'completed': set(),
    }

`PATCH /orders/{id}/status` with body `{"status": "accepted"}` (and so on).

Role gate, checked after the transition table:

- **Farmer** (must own the order): `accepted`, `rejected`, `completed`
- **Buyer** (must own the order): `cancelled` only
- **Admin**: any transition the table permits

`completed` is reachable only from `accepted`, so an order cannot skip the
farmer's approval.

## Reopen

`POST /orders/{id}/reopen` — farmer or admin only.

Only `rejected` and `cancelled` orders can be reopened. **`completed` is
final.** A buyer who wants more after delivery places a new order via
`POST /orders`.

**Quantity is capped on reopen.** The stock was returned when the order was
rejected, so by reopen time another buyer may have taken it. The reopened
quantity becomes `min(original_quantity, available_quantity)`, and
`total_amount` is repriced from the listing's current `price_per_unit`. If no
stock remains, the reopen returns 409 rather than overselling.

Worked example from the test suite:

    35 kg listed
    A orders 10 kg      -> available 25
    farmer rejects A    -> available 35
    B orders 30 kg      -> available 5
    farmer reopens A    -> A's quantity becomes 5, available 0

**Deviation from your wording, flagged:** you said "the consumer can only
enter the amount of stock left," which could mean the buyer re-types a
quantity after the farmer lifts the rejection. This builds automatic capping
instead — same guarantee, no second round-trip. If you wanted the buyer to
choose the new amount, that is a different flow and can be a follow-up.

## Buyer rejection cooldown

    BUYER_REJECTION_COOLDOWN_HOURS=48

After a farmer rejects a buyer's order on a listing, that buyer cannot place
another order **on that same listing** for 48 hours. Returns 429 with an
explanatory message. Enforced in `POST /orders`, before any stock moves.

- Scope: the same listing only. Other listings from the same farmer are open.
- Trigger: `rejected` only. Cancellations do not trigger it, whether the
  farmer or the buyer cancelled.
- Other buyers are unaffected.

**The reopen window is gone.** You said farmer and admin both bypass it, so
nothing was left to enforce. `REOPEN_WINDOW_DAYS` was replaced by this
cooldown, which is a different mechanism with a real enforcement point.
Shipping config that is read and ignored would have been worse than dropping it.

## Migration 0002

Adds `orders.status_changed_at`, non-null, `server_default CURRENT_TIMESTAMP`.

The cooldown needs to know *when* an order was rejected. `created_at` is not
that — an order can sit in `requested` for days before a farmer acts, and
counting from creation would shorten the cooldown unpredictably.

Existing rows are backfilled with the current timestamp by the server default,
which is safe: nothing can currently set a terminal status, so no historical
order is in a rejected state.

## Test harness

`conftest.py` builds an in-memory SQLite engine with `StaticPool` (without it,
each connection gets a fresh empty database and tables vanish between the
fixture and the request).

**`TestClient(app)` is deliberately not used as a context manager.** Starlette
only runs the startup lifespan inside `with`, so this skips `create_all()` and
`seed()` against your real database. Tests build their own schema.

Fixtures: `db`, `client`, `make_user`, `make_listing`, `auth`. An autouse
fixture drops and recreates all tables before each test.

## What is NOT tested

- The two pre-existing freshness tests are untouched and still run.
- No test covers `/dashboard/summary` or `GET /orders` listing.
- No test covers concurrent requests racing on the same listing. Reservation
  is a read-then-write in Python; two simultaneous requests could still both
  pass the stock check. Fixing that needs `SELECT ... FOR UPDATE` or a
  database-level constraint.

## Frontend impact

None, but behaviour changes:

- Placing an order now reduces the listing's `available_quantity`, so the
  marketplace shows fewer units ready after an order.
- A buyer rejected on a listing gets a 429 if they retry within 48 hours. The
  existing toast in `App.tsx` displays the message, since `api.request` throws
  `Error(detail)` on any non-2xx.
