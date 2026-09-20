# Dispatch #9 — Admin panel

## What this archive contains

Backend:

    FarmLink/backend/app/models/entities.py                        (moderation_note)
    FarmLink/backend/app/schemas/api.py                            (UserOut.is_active, 4 admin schemas)
    FarmLink/backend/app/api/routes.py                             (8 admin endpoints, metrics rewritten)
    FarmLink/backend/migrations/versions/0005_listing_moderation_note.py  (new)
    FarmLink/backend/tests/test_admin.py                           (new)

Frontend:

    FarmLink/frontend/src/types/index.ts          (AdminMetrics, AdminUser, AdminListing)
    FarmLink/frontend/src/lib/api.ts              (7 admin methods)
    FarmLink/frontend/src/pages/Admin.tsx         (new)
    FarmLink/frontend/src/components/Header.tsx   (Admin link)
    FarmLink/frontend/src/App.tsx                 (/admin route)

**No CSS change.** Reuses `.tabs`, `.order-card`, `.order-head`, `.order-status`,
`.metrics`, `.result-banner`, `.badge`, and `.empty`.

## How to apply

**SQLite:**

    cd E:\myApps\Project\FarmLink\backend
    del farmlink.db
    uvicorn app.main:app --reload

Delete again — `create_all()` never alters existing tables and `listings` needs
a new column. The seed repopulates users, categories, and listings. You lose
any orders placed while testing.

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

No new dependency this time.

## Deactivation already worked — this just exposes it

`security.py`'s `current_user` re-fetches the user on every request and rejects
`is_active == False`. That was already true before this dispatch. So
deactivating someone locks them out on their **next request**, not when their
JWT expires. `test_deactivated_user_is_rejected_on_every_request` proves it by
minting a token while active, deactivating, then reusing the same token.

Nothing needed to be added to auth. The flag simply had no endpoint and no UI.

## Lockout guards

Both are enforced server-side, not just by disabling a button:

    if target.id == user.id: 422 'You cannot change your own active status'
    if target.role == 'admin': 422 'Admin accounts cannot be deactivated'

An admin who deactivates themselves cannot sign back in to undo it. The same
goes for deactivating the only other admin. Neither is recoverable through the
UI, so neither is permitted.

## Listing moderation

Three statuses: `active`, `suspended`, `removed`. Both non-active states carry
an optional `moderation_note`.

- **Suspended** — reversible. Hidden from `/listings`, still reachable by direct
  URL, cannot be ordered (`create_order` already required `status == 'active'`).
- **Removed** — hidden from `/listings`, **and returns 404 from
  `/listings/{id}`**.

That 404 is a fix, not just a new rule. Before this dispatch `GET /listings/{id}`
returned any listing regardless of status, so removal would have been cosmetic —
the listing stayed fully visible to anyone with the URL.

The listing row is **retained** in the database. Order history references
`listing_id`, and deleting the row would break it.

## Removing a listing with open orders

Your choice: warn with the count, then act on confirmation.

    PATCH /admin/listings/{id}/status  { "status": "removed" }
    → 409 "This listing has 3 open orders. Confirm to cancel them and restore their reserved stock."

    PATCH /admin/listings/{id}/status  { "status": "removed", "cancel_open_orders": true }
    → 200 { ..., "cancelled_orders": 3 }

On confirmation, each open order (`requested` or `accepted`) is cancelled and its
reserved quantity returned to `available_quantity` — the same rule as a buyer
cancelling. `completed`, `rejected`, and `cancelled` orders are untouched.

`GET /admin/listings` includes an `open_orders` count per listing, computed in
one grouped query rather than one per row, so the UI can show the warning
without a second request.

## Categories

    POST   /admin/categories          create, unique name required
    PATCH  /admin/categories/{id}     rename and/or change default lifespan
    DELETE /admin/categories/{id}     blocked when listings reference it

Deletion is blocked rather than silently reassigning, because reassigning would
quietly change what produce a listing claims to be. The 409 carries the count:

> This category is used by 12 listings. Move them to another category before deleting.

Rename re-checks uniqueness, since `Category.name` is `UNIQUE`.

## Metrics — the last fabricated value is gone

Was:

    { users, listings, orders, subscriptions: 3 }

`subscriptions: 3` was hardcoded because subscriptions do not exist as a model.
Now:

    { users, listings, orders, reports_open, categories }

`reports_open` and `categories` were added because they are real, computable, and
useful. **`subscriptions` is not present at all** rather than being present and
fake. It returns when there is a table behind it — subscriptions remain a
planned feature.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **81 passed** (63 from before + 18 admin).

Then in the browser as `admin@farmlink.demo` / `Demo123!`:

1. The header shows an **Admin** link. Go to `/admin`.
2. **Overview** — five real counts, no subscriptions line.
3. **Users** — every account listed. Your own row's Deactivate button is
   disabled with "That is your own account."
4. Deactivate `buyer@farmlink.demo`. In another browser or incognito, sign in as
   that buyer — you should get "This account has been deactivated."
5. **Listings** — every listing with status and open-order count.
6. Suspend one. It disappears from `/marketplace`.
7. **Categories** — try deleting `Tomato`. Blocked with the listing count.
8. **Reports** — anything filed in dispatch #7 shows here with reporter, reason,
   and details.

Step 4 is the one that proves deactivation actually locks someone out.

## Known limitations

- **Deactivating a farmer does NOT touch their listings.** This is the most
  important gap. A deactivated farmer's listings stay `active` and orderable,
  and buyers can place orders that nobody will fulfil. The admin must suspend
  the listings manually. The alternative — cascading deactivation to listings,
  and reactivating them on restore — was not specified, so it was not invented.
  Worth deciding explicitly.
- **No reports workflow.** Reports are visible and that is all. No resolve,
  dismiss, or note. `Report.status` exists and defaults to `'open'`, but nothing
  changes it. `reports_open` in metrics therefore equals the total report count.
- **`window.prompt` for category rename.** Ugly and unstyleable, but it avoids
  adding a modal pattern for one field.
- **Admin sees the buyer view on `/orders`.** `Orders.tsx` branches on
  `role === 'farmer'`, so an admin gets the buyer layout with no action buttons.
  They can moderate listings but not touch orders from that page, even though
  `update_order_status` permits admins any transition. No admin order UI exists.
- **No user search or pagination.** Every user, listing, and report loads at
  once. Fine at demo scale.
- **No audit log.** `moderation_note` records the last reason on a listing.
  Nothing records who changed what and when.
- **Deactivated users are invisible in the listing flow.** A suspended farmer
  cannot sign in to see their own dashboard, and `/auth/me` returns 401, so the
  frontend clears the token. There is no "your account was deactivated" page —
  just a failed sign-in.
