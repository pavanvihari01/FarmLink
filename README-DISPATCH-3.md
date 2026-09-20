# Dispatch #3 — Real dashboard metrics

## What this archive contains

    FarmLink/backend/app/api/routes.py        (two endpoints added)
    FarmLink/frontend/src/types/index.ts      (DashboardSummary type)
    FarmLink/frontend/src/lib/api.ts          (summary method)
    FarmLink/frontend/src/pages/Dashboard.tsx (rewritten)

No migration. No schema change. No CSS change. No new dependency.

## How to apply

Unzip at the project root:

    E:\myApps\Project

Restart the backend (routes changed, `--reload` should pick it up but a
restart is cleaner), then:

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build
    pnpm dev

## What changed

### Dashboard metrics are no longer hardcoded

Before, `Dashboard.tsx` rendered literal strings:

    <strong>{user.role === 'farmer' ? '7' : '24'}</strong>
    <strong>{user.role === 'farmer' ? '4' : '2'}</strong>
    <strong>{user.role === 'farmer' ? 'High' : '5'}</strong>

A freshly registered farmer saw "7 active listings" and "High expected
demand". Both were fiction. Every number now comes from the database.

### New endpoint: `GET /dashboard/summary`

Role-aware. Reads the JWT, branches on `user.role`.

**Farmer** returns:

| Key | Meaning |
| --- | --- |
| `active_listings` | Own listings where `status == 'active'` **and** not expired |
| `open_orders` | Incoming orders whose status is not terminal |
| `expired_listings` | Own listings whose freshness window has passed |

**Buyer** (and anyone who is not a farmer — see limitations) returns:

| Key | Meaning |
| --- | --- |
| `available_now` | Listings with `status == 'active'` and not expired. Same set `/listings` returns. |
| `open_orders` | Own orders whose status is not terminal |
| `categories` | Distinct `category_id` across those listings |

`active_listings` and `expired_listings` are disjoint, so they sum to the
farmer's total active-status listings. That is deliberate — a listing should
never be counted as both live and expired.

### Counting uses the real freshness function

`freshness()` in `app/services/freshness.py` is a plain Python function that
takes an ORM object, not a SQL expression. So the counts load rows and call it,
exactly the way the existing `/listings` route already does:

    [x for x in rows if freshness(x)[0] != 'Expired']

Reimplementing the thresholds in SQL would have duplicated the logic and let
the two drift. At demo scale, loading a few dozen rows is free.

### New endpoint: `GET /orders`

Role-aware list. A farmer sees orders where they are the farmer, with the
buyer's name as `counterparty`. A buyer sees their own orders, with the
farmer's name. Sorted newest first.

Each row returns:

    { id, listing_id, listing_title, counterparty, quantity,
      total_amount, status, created_at }

**This endpoint is not consumed by the dashboard in this dispatch.** It exists
because the order-count endpoint shape was chosen as `GET /orders`, and it is
the foundation for the buyer order-history and farmer order-management phases.
Flagging that plainly rather than leaving an unused endpoint undocumented.

### Terminal order statuses

    TERMINAL_ORDER_STATUSES = {'completed', 'cancelled', 'rejected'}

`open_orders` counts orders whose status is **not** in that set. Today no
endpoint can set those statuses — every order is created as `'requested'` and
nothing transitions it — so `open_orders` currently equals the total order
count. The set is defined now so the count stays correct once the status
transitions land, rather than silently over-counting finished orders later.

### Loading and error states

`Dashboard.tsx` renders `—` (em dash) for any metric before the fetch resolves,
and shows the error message above the cards if the request fails. Previously
the numbers appeared instantly because they were literals; now there is a real
request, so there is a real loading state.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    uvicorn app.main:app --reload

In another terminal:

    curl -H "Authorization: Bearer <farmer token>" http://localhost:8000/dashboard/summary
    curl -H "Authorization: Bearer <buyer token>"  http://localhost:8000/dashboard/summary

Get a token from:

    curl -X POST http://localhost:8000/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email":"farmer@farmlink.demo","password":"Demo123!"}'

Then in the browser:

1. Sign in as `farmer@farmlink.demo`. The dashboard should show **6** active
   listings and **0** open orders (the seed creates six listings, no orders).
2. Sign in as `buyer@farmlink.demo`. Should show **6** available now, **0** open
   orders, **5** categories.
3. Place an order from `/marketplace` as the buyer. The buyer's open orders
   goes to 1.
4. Register a brand-new farmer via `/register`. Their dashboard must show
   **0 / 0 / 0**, not the old hardcoded 7 / 4 / High.

Step 4 is the one that actually proves this dispatch worked.

## Known limitations

- **Admin falls into the buyer branch.** `dashboard_summary` branches on
  `role == 'farmer'`; anything else gets the buyer shape. An admin sees
  available-now and categories for their own (nonexistent) orders. Admin
  metrics are their own phase.
- **`/admin/metrics` still returns `subscriptions: 3`.** A hardcoded value in
  the same file. Out of scope here — subscriptions do not exist as a model —
  but it is the last fabricated number in the API.
- **Both counts load every row into Python.** Fine at demo scale. At thousands
  of listings this needs the freshness thresholds pushed into SQL.
- **`expired_listings` counts expired listings regardless of `status`.** If a
  listing were ever manually delisted, it would still count as expired. No
  endpoint can currently set a non-active status, so this cannot happen today.
