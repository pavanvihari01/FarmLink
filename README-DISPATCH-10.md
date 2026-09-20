# Dispatch #10 — Marketplace search, sort, pagination, and listing detail

## What this archive contains

Backend:

    FarmLink/backend/app/models/entities.py                        (expires_at)
    FarmLink/backend/app/services/freshness.py                     (prefers the stored column)
    FarmLink/backend/app/api/routes.py                             (GET /listings rewritten, recommendations fixed)
    FarmLink/backend/migrations/versions/0006_listing_expires_at.py (new)
    FarmLink/backend/tests/conftest.py                             (make_listing gains age_hours, category)
    FarmLink/backend/tests/test_listings_query.py                  (new)

Frontend:

    FarmLink/frontend/src/types/index.ts          (ListingQuery, PaginatedListings, richer Listing)
    FarmLink/frontend/src/lib/api.ts              (query-string builder, listings(), listing())
    FarmLink/frontend/src/lib/useGeolocation.ts   (new)
    FarmLink/frontend/src/pages/Marketplace.tsx   (rewritten)
    FarmLink/frontend/src/pages/ListingDetail.tsx (new)
    FarmLink/frontend/src/components/ProductCard.tsx (links to detail, shows distance)
    FarmLink/frontend/src/pages/Orders.tsx        (View listing points at the detail page)
    FarmLink/frontend/src/pages/Admin.tsx         (View pointed at the wrong page — fixed)
    FarmLink/frontend/src/App.tsx                 (detail route, featured strip)

**No CSS change and no new dependency.**

## How to apply

**SQLite:**

    cd E:\myApps\Project\FarmLink\backend
    del farmlink.db
    uvicorn app.main:app --reload

Delete again — `create_all()` never alters existing tables and `listings` needs
the new `expires_at` column. Migration 0006 backfills it, but that only runs
under Alembic; on SQLite the seed recreates listings with it set.

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

## BREAKING: `GET /listings` returns an envelope, not an array

Was:

    [ {...}, {...} ]

Now:

    {
      "items": [ {...}, {...} ],
      "total": 42,
      "page": 1,
      "pages": 4,
      "page_size": 12
    }

Every caller had to change. `App.tsx` reads `.items` for the home strip;
`Marketplace.tsx` reads the whole envelope. **`recommendations` was the subtle
one** — it called the `/listings` route *function* directly, which no longer has
that shape, so its logic is now written out separately.

## Query parameters

| Param | Type | Notes |
| --- | --- | --- |
| `q` | text | Matches title or location, case-insensitive |
| `category_id` | int | |
| `min_price` / `max_price` | float | |
| `organic` | bool | |
| `bulk_available` | bool | |
| `location` | text | Substring of `location_text` |
| `farmer` | text | Substring of the farmer's name |
| `freshness_status` | `Fresh` / `Use Soon` / `Expiring` | 422 on anything else |
| `sort` | `freshness` / `price_asc` / `price_desc` / `newest` / `nearest` | Default `freshness` |
| `page` | int ≥ 1 | Clamps to the last page if past the end |
| `page_size` | int 1–48 | Default 12 |
| `lat` / `lng` | float | Required for `nearest`; optional otherwise, adds `distance_km` |

## Sorting and filtering happen in Python, not SQL

You chose server-side, and it is — the browser sends parameters and receives one
page. But the work happens in Python after SQL narrows what it can.

Why: freshness is a **ratio**, not a timestamp. `Fresh` means
`remaining / lifespan_hours > 0.6`, and distance needs haversine. Neither is
expressible portably across SQLite and PostgreSQL, and writing two SQL dialects
to keep in sync is worse than one Python path.

What that costs: **the filtered set is materialised in memory on every
request.** At 6 seeded listings this is nothing. At 10,000 it is a problem, and
the fix is to push the ratio thresholds into SQL using `expires_at` and
`lifespan_hours` arithmetic — which is what the column exists to enable.

The one exception is the initial SQL `WHERE`: status, category, price, flags,
and text are all filtered in the database, so the set that reaches Python is
already smaller than the table.

## Why `expires_at` exists

Before this, every freshness check recomputed `(harvest_time or listing_time) +
lifespan_hours`. Storing it:

- makes the value consistent across the sort path and the display path
- gives an index for the common `expires_at > now` filter
- makes a future SQL-side sort a one-line change

`freshness()` still accepts plain objects without the column and falls back to
computing — which is why the existing freshness tests, built on
`SimpleNamespace`, still pass untouched.

## The listing detail page

`/listings/:id` — photo, description, farmer, location, price, available
quantity, remaining life, organic and bulk flags, quantity picker capped at
stock, add to cart, report link.

**Scope note:** you chose "Standard", which does not include a map. The listing's
coordinates are returned by the API and the card shows distance when known, but
the detail page shows no pin. Adding a read-only map is a small follow-up.

`Admin.tsx`'s "View" link was pointing at `/report/${id}` — the report form, not
the listing. That was wrong and is now `/listings/${id}`.

## Distance

Browser geolocation, requested **only** when the buyer picks "Nearest to me".
It is not requested on page load, because prompting someone who never wanted
distance sorting is hostile. The result is cached in `localStorage`, so the
permission prompt appears once.

If permission is declined, the page says so and offers to switch back to
freshness sorting. It does not silently fall back, because a sort control that
claims "nearest" while doing something else is a lie.

Listings with no coordinates sort **last** under `nearest`, not first. Treating
a missing pin as distance zero would put every un-pinned listing at the top.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **105 passed** (81 from before + 24 listings-query).

Then in the browser:

1. `/marketplace` — 6 listings, "6 listings available today".
2. Change sort to **Price: low to high**. Order changes immediately, no debounce.
3. Open **More filters**, set Max price to 45. Count drops.
4. Tick **Organic only**. Count drops further.
5. Clear all. Count returns to 6.
6. Type in the search box. **Wait ~350ms** — that is the debounce.
7. Set sort to **Nearest to me**. The browser asks for location. Allow it. Each
   card gains a "N km from you" line.
8. Click a card title. `/listings/:id` opens with description and a quantity
   picker. Set quantity 3, **Add to cart**. The header badge shows 3.
9. In incognito, set sort to Nearest and **decline** the prompt. The page says
   location was declined and offers to switch back.

Step 7 and step 9 are the ones that prove the geolocation path is honest.

## Known limitations

- **The filtered set is loaded into memory.** Described above. This is the
  headline cost of the design and the first thing to change at scale.
- **Seeded listings have no coordinates.** Only listings created through the
  map picker have them, so `nearest` puts all six seeded listings last. To try
  the feature properly, create a listing with a pin first.
- **No map on the detail page**, by scope.
- **Pagination renders every page number.** At 4 pages that is fine; at 40 it
  needs a windowed control.
- **Filter state is not in the URL.** Reloading `/marketplace` resets every
  filter. Sharing a filtered link does not work. Moving the filters into
  `useSearchParams` is the fix and is self-contained.
- **No price slider.** Min and max are number inputs, per the chosen option.
- **`organic` and `bulk_available` are stored and filterable but nothing sets
  them except the create-listing form's checkboxes.**
- **Text search is a substring match.** No stemming, no ranking, no fuzzy
  matching. `tomato` finds `Vine-ripe Tomatoes` but `tomatoes` and `tomatoe`
  behave differently.
- **Distance is straight-line.** No roads, no travel time.
- **`expires_at` is not updated when a farmer edits a listing** — because
  nothing can edit a listing yet. When edit lands, `expires_at` must be
  recomputed there too, and that is easy to forget.
