# Dispatch #7 — Reporting system

## What this archive contains

Backend:

    FarmLink/backend/app/models/entities.py                       (Report model)
    FarmLink/backend/app/schemas/api.py                           (ReportInput)
    FarmLink/backend/app/api/routes.py                            (3 report endpoints)
    FarmLink/backend/app/core/config.py                           (REPORT_LOCK_THRESHOLD, UPLOAD_DIR)
    FarmLink/backend/migrations/versions/0004_reports.py          (new)
    FarmLink/backend/tests/test_reports.py                        (new)
    FarmLink/backend/.env.example                                 (one var added)

Frontend:

    FarmLink/frontend/src/pages/Report.tsx        (new)
    FarmLink/frontend/src/types/index.ts          (Report types)
    FarmLink/frontend/src/lib/api.ts              (4 methods)
    FarmLink/frontend/src/components/ProductCard.tsx  (optional report link)
    FarmLink/frontend/src/pages/Marketplace.tsx   (passes onReport)
    FarmLink/frontend/src/pages/Orders.tsx        (correction + report link)
    FarmLink/frontend/src/App.tsx                 (/report/:listingId route)

**No CSS change.** Reuses `.cart-summary`, `.order-card`, `.error`, and
`.result-banner`.

## Why this dispatch exists before the create-listing form

You asked for the "lock lifespan for reported users" rule. That rule needs a
report count to read. There was no reports table, no endpoint, and no way to
file a report — so the rule had nothing to stand on. This builds the thing it
needs. The lock itself lands in dispatch #8.

## Scope note — your two answers disagreed

You said *"build a minimal reporting system first as its own dispatch, then
come back to #7"*, and also *"#7 is now: upload + mount + proxy + Leaflet +
form, don't split."*

Read together: this is the reporting dispatch, and the create-listing form
follows as #8, unsplit. Say so if that is not what you meant.

## How to apply

**SQLite (your setup):**

    cd E:\myApps\Project\FarmLink\backend
    del farmlink.db
    uvicorn app.main:app --reload

Delete again — `create_all()` never alters existing tables and `reports` is a
new table. The seed repopulates users, categories, and listings. You lose any
orders placed while testing.

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

## The deduplication constraint, and why it matters

    UNIQUE (reporter_id, listing_id)

One report per buyer per listing. Without it, a single buyer could file ten
reports on one listing and single-handedly cross the lock threshold of 3.
Their reports would be indistinguishable from three different buyers agreeing.

The constraint does **not** limit how many different listings one buyer can
report. `test_a_single_buyer_cannot_trip_the_lock_alone` documents this
honestly: three reports from one buyer on three listings still count as three.
Tightening that would need per-buyer weighting or a distinct-reporter count,
which is a moderation policy decision, not a code one.

## Endpoints

### `POST /reports`

    { "listing_id": 4, "reason": "fake_lifespan", "details": "..." }

`reported_user_id` is **derived server-side** from the listing's farmer. The
client cannot claim a different reported user than the listing owner.

Rejections: 404 unknown listing, 422 own listing, 422 invalid reason, 409
already reported, 401 anonymous.

### `GET /reports`

Admin only (403 otherwise). Optional `?status=open`. Joins in the reporter's
name, the reported user's name, and the listing title.

### `GET /reports/against-me`

    { "count": 3, "threshold": 3, "locked": true }

This is what dispatch #8's create-listing form reads to decide whether the
`lifespan_hours` field is editable.

## Frontend

`ProductCard` gained an optional `onReport`. Only `Marketplace` passes it, so
the link appears there and not on the home page or dashboard.

`/report/:listingId` renders the reason picker, an optional details box, and a
submit. Signed-out visitors get a sign-in prompt instead of the form. The order
card also links here, so a buyer can report after receiving an order.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **42 passed** (2 freshness + 19 order + 9 checkout + 12 reports).

Then in the browser:

1. Sign in as `buyer@farmlink.demo`. Go to `/marketplace`.
2. Each card shows a small **Report this listing** link under the button.
3. Click it. Pick a reason, submit.
4. **The same link on the same listing now returns "You have already reported
   this listing"** if you try again.
5. Sign in as `farmer@farmlink.demo`. Open the browser console and run:
   `fetch('http://localhost:8000/reports/against-me', {headers:{Authorization:'Bearer '+localStorage.token}}).then(r=>r.json()).then(console.log)`
   → `{count: 1, threshold: 3, locked: false}`

## Known limitations

- **Reports do not affect anything yet.** Nothing hides a reported listing,
  suspends a farmer, or locks the lifespan field. `locked` is computed and
  returned but no caller acts on it until #8.
- **No UI to review reports.** `GET /reports` exists and is admin-gated, but
  the admin panel is dispatch #9. Reports currently accumulate invisibly.
- **Reports cannot be withdrawn.** One report per listing, permanently.
- **No notification to the farmer.** A farmer learns of a report only by
  checking `against-me`.
- **Reason is a fixed set.** Adding a reason means a schema change.
- **`UPLOAD_DIR` was added to `config.py` but nothing uses it yet.** It is
  there for #8, which adds the upload endpoint. Flagging it so it does not look
  like dead config.
