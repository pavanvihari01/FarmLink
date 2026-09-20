# Dispatch #15 — Closing the known gaps

## What this archive contains

    backend/app/models/entities.py                              (2 columns)
    backend/app/schemas/api.py                                  (4 new schemas, 2 extended)
    backend/app/api/routes.py                                   (7 new endpoints, 4 modified)
    backend/app/services/images.py                              (new)
    backend/migrations/versions/0009_farmer_controls.py         (new)
    backend/tests/test_fixes.py                                 (new)

    frontend/src/types/index.ts
    frontend/src/lib/api.ts
    frontend/src/context/CartContext.tsx
    frontend/src/components/LocationPicker.tsx
    frontend/src/components/DeliveryMiniMap.tsx                 (new)
    frontend/src/pages/EditListing.tsx                          (new)
    frontend/src/pages/ListingDetail.tsx
    frontend/src/pages/Dashboard.tsx
    frontend/src/pages/Profile.tsx
    frontend/src/pages/Cart.tsx
    frontend/src/pages/Orders.tsx
    frontend/src/pages/Admin.tsx
    frontend/src/App.tsx

**Commit before extracting.** Twenty files, one of them 1100 lines. If
something breaks, you want a clean revert point.

## How to apply

**SQLite:**

    cd E:\myApps\Project\FarmLink\backend
    del farmlink.db
    uvicorn app.main:app --reload

Delete the database — two new columns, and `create_all()` will not add them.

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

## The eleven fixes

### 1. Listing edit and delete

`PATCH /listings/{id}` and `DELETE /listings/{id}`, plus a new
`GET /farmer/listings` that shows the farmer their own listings whatever their
status — the public endpoint hides suspended and expired rows, so there was no
way for a farmer to reach them.

The edit form is at `/listings/:id/edit`. The farmer reaches it from their
dashboard or from the listing's own page, which now shows an **Edit listing**
button instead of an add-to-cart for the owner.

**`expires_at` is recomputed on every edit.** Leaving it stale was the
correctness gap #10 flagged. Recomputing unconditionally is idempotent when
nothing that feeds it changed, so there is no branch to get wrong.

**The report lock applies to edits.** Without that, a farmer whose lifespan was
capped by reports could edit their way around it.

**Delete is a soft delete** — status becomes `removed`, matching the admin flow
from #9. Order history keeps resolving. Open orders block the removal with a
409 unless `?cancel_open_orders=true`, in which case they are cancelled and
their reserved stock returns.

### 2. Deactivating a farmer cascades to their listings

New column `listings.suspended_by_deactivation`.

Deactivating suspends the farmer's **active** listings and flags them.
Reactivating restores **only those** — a listing an admin suspended by hand
stays suspended.

Any manual status change by an admin clears the flag, so an admin who suspends
an already-auto-suspended listing does not find it silently restored later.

`PATCH /admin/users/{id}/active` returns `listings_affected`, and the admin UI
warns before deactivating a farmer who has listings.

### 3. Report resolve and dismiss

`PATCH /admin/reports/{id}` with `{status: 'resolved'|'dismissed', note?}`.
Only from `open`, one-way. New `reports.resolution_note` column.

**Resolving does not touch the listing or the farmer.** It records that an admin
looked. Any action is separate. `reports_open` in the metrics now actually
falls when reports are closed — previously it could only ever equal the total.

### 4. Password change

`POST /auth/change-password` with current and new password. Minimum 8
characters, must differ from the current one.

**Existing tokens are not invalidated.** The JWT carries only the user id and
role, no password material. A device signed in before the change stays signed
in until its token expires. Flagged below.

### 5. Address edit and set-default

`PATCH /addresses/{id}`. Every field optional. `latitude: null` clears the pin.
`is_default: true` demotes whichever address held it; `false` is ignored,
because a user with any addresses must always have exactly one default.

The profile page gained inline editing — click the pencil, the card becomes a
form.

### 6. Upload magic-byte validation

New `app/services/images.py` sniffs the actual bytes. JPEG, PNG, and WebP
signatures are checked, and the result must match the declared content type.

Previously a file named `.jpg` containing HTML would be stored and served back
as `image/jpeg`. **This is a signature check, not a decode** — a file with valid
JPEG magic bytes followed by arbitrary data still passes. Full validation needs
Pillow, which is not a dependency.

### 7. Image cleanup

**On replacement, not on removal.** When a farmer edits a listing and points it
at a different image, the old file is deleted if no other listing references it.

Removal deliberately does NOT delete the image: the listing row survives a soft
delete, and restoring it would leave a broken card.

The bundled default `/images/market-harvest.png` is never touched — it is shared
by every listing that never uploaded one.

### 8. Cart refetches prices

`CartContext` gained `refreshFrom(listings)`. The cart page calls it once on
mount with fresh data.

The cart stores snapshots taken when items were added, so a price a farmer
changed last week still showed — and the order was charged at the new price.
Now prices, units, and remaining stock are reconciled, and anything no longer
available is dropped with a message saying what went.

### 9. Map re-centres

`LocationPicker` gained a `FollowPin` child that calls `map.setView` when the
coordinates change. `MapContainer` reads `center` only on mount, so dropping a
pin elsewhere — or clearing one — previously left the view where it started.

### 10. Admin order UI

New `GET /admin/orders` and an **Orders** tab in the admin panel.

Admins could already transition any order through `PATCH /orders/{id}/status` —
`update_order_status` permits it — but there was no list to act on. There is
now. No pagination.

### 11. Buyer delivery map

`DeliveryMiniMap` renders on a buyer's order card when the order is a delivery
and the address was pinned. Read-only: dragging and scroll zoom off.

**This loads Leaflet on the orders page**, adding roughly 150 KB to a route that
previously did not need it.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **208 passed** (185 from before + 23 gap-closing tests).

Then in the browser:

1. As `farmer@farmlink.demo`, go to `/dashboard`. **Your listings** appears with
   an Edit link on each.
2. Edit one. Change the price, drop a pin, replace the photo. Save.
3. The old photo file is gone from `backend/uploads/`; the new one is there.
4. Remove a listing. It disappears from `/marketplace` and shows `removed` on
   your dashboard, still listed.
5. As `admin@farmlink.demo`, deactivate that farmer. The banner reports how many
   listings were suspended.
6. Reactivate. **Only the auto-suspended ones come back** — anything you
   suspended by hand before stays suspended.
7. As `buyer@farmlink.demo`, add two things to the cart, then have the farmer
   change one price. Reload `/cart`. The price updates.
8. File a report as a buyer. As admin, open **Reports**, resolve it with a note.
   The Overview tab's **Open reports** count drops.
9. Change your password on `/profile`. Sign out, sign back in with the new one.

Step 6 is the one that proves the cascade flag works. Step 7 proves the cart
reconciliation.

## Known limitations

- **Existing tokens survive a password change.** Nothing invalidates them. A
  proper fix needs a token version column or a denylist, which is its own
  dispatch.
- **Cart refresh runs only when the cart page opens.** A price that changes
  while the cart sits open in another tab is not noticed until reload.
- **Image cleanup happens on replacement, not on removal.** Soft-deleted
  listings keep their photos forever, because the delete is reversible.
  A purge job for long-removed listings is not built.
- **Magic bytes are a signature check.** A crafted file with valid JPEG magic
  bytes passes. Decoding needs Pillow.
- **Admin orders has no pagination.** Every order loads at once.
- **The buyer's delivery map loads Leaflet** on the orders page, whether or not
  the buyer has a pinned delivery.
- **Report resolution notifies nobody.** The reporter does not learn their
  report was closed.
- **No report reopen.** Closing is one-way, so `reports_open` stays meaningful.
- **`routes.py` is now ~1100 lines.** Splitting it into per-domain routers
  (`listings.py`, `orders.py`, `admin.py`, …) is a worthwhile refactor that was
  not part of this dispatch. Everything still works; it is just harder to
  navigate.
- **Listing edit does not warn about concurrent changes.** Two tabs editing the
  same listing, last write wins.
