# Dispatch #12 — Subscriptions

## What this archive contains

Backend:

    FarmLink/backend/app/models/entities.py                    (Subscription, SubscriptionCycle, orders.subscription_id)
    FarmLink/backend/app/schemas/api.py                        (FarmerOut, SubscriptionInput)
    FarmLink/backend/app/api/routes.py                         (subscription endpoints, GET /farmers)
    FarmLink/backend/migrations/versions/0007_subscriptions.py (new)
    FarmLink/backend/tests/test_subscriptions.py               (new)

Frontend:

    FarmLink/frontend/src/types/index.ts        (Subscription, SubscriptionCycle, Farmer)
    FarmLink/frontend/src/lib/api.ts            (5 subscription methods, farmers())
    FarmLink/frontend/src/pages/Subscriptions.tsx (new)
    FarmLink/frontend/src/components/Header.tsx (Subscriptions link)
    FarmLink/frontend/src/App.tsx               (/subscriptions route)
    FarmLink/frontend/src/pages/Admin.tsx       (Subscriptions tab)

**No CSS change and no new dependency.**

## How to apply

**SQLite:**

    cd E:\myApps\Project\FarmLink\backend
    del farmlink.db
    uvicorn app.main:app --reload

Delete the database — `create_all()` never alters existing tables, and this
adds two tables plus a column on `orders`.

**PostgreSQL:**

    cd E:\myApps\Project\FarmLink
    docker compose up -d db
    cd backend
    alembic upgrade head
    uvicorn app.main:app --reload

Then:

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build
    pnpm dev

## What a subscription is

A standing arrangement between one buyer and one farmer for one category.

**Not** a specific listing. A listing expires within hours to days, so "weekly
5kg of Vine-ripe Tomatoes" would break the moment that row expires. Instead the
buyer names a farmer and a category, and each cycle the **freshest matching
listing** is chosen for them. The buyer sees which order came from which cycle.

`quantity` and `unit` are fixed at creation. The unit must match the listing's
unit at generation time — without that check, "5" against a listing priced per
dozen instead of per kg would silently order five dozen.

## There is no scheduler, so generation is lazy

Nothing in this project runs on a timer. Cycles are generated when either party
opens `/subscriptions`:

    POST /subscriptions/generate-due   →   GET /subscriptions

Two calls rather than one, deliberately. Generation is a **write**, and a GET
that writes is a trap for anyone using the API directly. The page makes both
calls on mount.

### Only the most recent due cycle is fulfilled

A subscription nobody looked at for ten weeks does **not** produce ten orders.
Older cycles are recorded as `skipped` with reason "Missed — the subscriptions
page was not opened in time", because whatever was fresh then expired long ago.
Only the current cycle is actually attempted.

`test_a_long_absence_does_not_pile_up_orders` asserts this: 10 weeks behind
produces 1 order and 9+ skips.

### Idempotent, including under a race

`next_cycle_at` advances by one frequency in the same commit as the cycle row.
The unique constraint on `(subscription_id, scheduled_for)` means two page
loads arriving at once cannot both record the same cycle — the second insert
fails, the whole generation rolls back, and the next call finds nothing due.

That constraint is also why the race handling works identically on SQLite and
PostgreSQL. Row locking would not.

## A cycle is skipped when…

- the farmer has no active listing in that category
- the only listings are expired
- available quantity is less than the subscription quantity
- the listing's unit does not match the subscription's unit

In every case a `subscription_cycles` row records the reason, and the buyer sees
it under **Recent cycles** on the subscription card. The next cycle date still
advances — a skipped cycle is not retried.

## Cancellation

**Buyer and farmer have no control over the lifecycle.** No pause, no cancel.
This was the chosen rule, not an oversight — the UI states it plainly on every
active subscription.

**Admin can cancel any subscription**, from the new Subscriptions tab or via
`DELETE /admin/subscriptions/{id}`. Cancelling stops future cycles; orders
already generated are untouched.

## `GET /farmers`

New. Returns active farmers as `{id, name, location}` for the subscription
form's picker. Every farmer is listed regardless of current stock — a buyer may
want to subscribe ahead of a harvest. The form shows what will happen when
nothing is available, rather than blocking the choice.

## `subscriptions` is back in `/admin/metrics`

Dispatch #9 removed the hardcoded `subscriptions: 3` because there was no table
behind it. There is now, so the key returns — as a real count of *active*
subscriptions.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **132 passed** (105 from before + 27 subscriptions).

Then in the browser:

1. Sign in as `farmer@farmlink.demo` and create a listing in a category — say
   Tomato. Note the unit you chose.
2. Sign out. Sign in as `buyer@farmlink.demo`. The header shows **Subscriptions**.
3. Go to `/subscriptions`. Pick the farmer, the same category, quantity 5, and
   the **same unit** you used in step 1. Frequency: every week.
4. Subscribe. The card shows "Next box" one week out.
5. To see generation without waiting a week, backdate it in the database:
```

cd E:\myApps\Project\FarmLink\backend
python -c "import sqlite3; c=sqlite3.connect('farmlink.db'); c.execute("UPDATE subscriptions SET next_cycle_at = datetime('now','-1 day')"); c.commit()"

```
6. Reload `/subscriptions`. A banner reports the cycle, and the card lists it
under **Recent cycles** as an order.
7. `/orders` — the new order is there. Its quantity is 5 and the marketplace
listing's stock dropped by 5.

Step 6 is the one that proves lazy generation works end to end.

## Known limitations

- **No scheduler.** Cycles only exist because someone opened a page. A buyer
who never visits gets nothing. A real deployment needs a timer, which is a
new dependency and a new process.
- **Nobody can pause.** A buyer going away for a month cannot stop the boxes
without asking an admin. Pause/resume was not in the chosen rules.
- **No subscription editing.** Quantity, unit, frequency, address, and payment
are fixed at creation. Changing any of them means admin cancellation and a new
subscription.
- **The unit must match exactly.** `kg` and `g` are different units, so a
subscription in grams will never match a listing in kilograms even though
they are convertible. No unit conversion exists.
- **Generation is per-viewer.** Opening the page as the buyer generates only
the buyer's subscriptions; the farmer's visit generates theirs. If neither
visits, nothing happens for anyone.
- **`GET /subscriptions` does not generate.** Callers must POST
`/subscriptions/generate-due` first. The UI does; a direct API user has to
know to.
- **No notification.** "Tell the buyer" means the reason is visible on the
subscriptions page. Nothing is emailed or pushed.
- **A cancelled subscription still appears in the list** with its cycle
history. There is no delete.
- **No admin UI to view a subscription's cycle history.** The admin tab shows
the arrangement and lets you cancel; per-cycle detail is buyer/farmer side
only.
