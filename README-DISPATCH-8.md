# Dispatch #8 — Create-listing form with upload and map

## What this archive contains

Backend:

    FarmLink/backend/requirements.txt                  (python-multipart added)
    FarmLink/backend/app/main.py                       (static mount for /uploads)
    FarmLink/backend/app/api/routes.py                 (upload endpoint, lifespan enforcement)
    FarmLink/backend/tests/test_uploads.py             (new)
    FarmLink/backend/tests/test_listing_create.py      (new)
    FarmLink/backend/uploads/.gitignore                (new)

Frontend:

    FarmLink/frontend/package.json                     (@types/leaflet added)
    FarmLink/frontend/vite.config.ts                   (/uploads dev proxy)
    FarmLink/frontend/src/types/index.ts               (Category type)
    FarmLink/frontend/src/lib/api.ts                   (categories, createListing, uploadImage)
    FarmLink/frontend/src/components/LocationPicker.tsx  (new)
    FarmLink/frontend/src/pages/CreateListing.tsx      (new)
    FarmLink/frontend/src/pages/Dashboard.tsx          (Create listing CTA)
    FarmLink/frontend/src/components/Header.tsx        (Sell link for farmers)
    FarmLink/frontend/src/App.tsx                      (/listings/new route)

**No CSS change and no migration.** `image_url`, `latitude`, and `longitude`
already exist on `listings`.

## How to apply

Unzip at the project root, then install the two new dependencies:

    cd E:\myApps\Project\FarmLink\backend
    pip install -r requirements.txt          # brings in python-multipart

    cd E:\myApps\Project\FarmLink\frontend
    pnpm install                             # brings in @types/leaflet

Then:

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build
    pnpm dev

**The backend must be restarted**, not just reloaded — `main.py` gained a
static mount, which is set up at import time.

No database change is needed. If you are on SQLite you do NOT have to delete
`farmlink.db` this time.

## Two dependencies that would break the build if omitted

- **`python-multipart`** — FastAPI's `UploadFile` / `File()` raise at import
  time without it. The upload endpoint cannot even be defined.
- **`@types/leaflet`** — Leaflet ships no bundled types, and `react-leaflet`'s
  own declarations import from `'leaflet'`. Under `strict`, TypeScript reports
  "Could not find a declaration file for module 'leaflet'" and `pnpm build`
  fails.

## Image URL handling — exactly as specified

    Browser :5173  →  /uploads/abc.jpg
                   →  Vite dev proxy
                   →  FastAPI :8000  →  /uploads/abc.jpg

- Database stores **relative** paths: `/uploads/<uuid>.jpg`
- `vite.config.ts` proxies **only** `/uploads`
- `/api` calls are untouched — `lib/api.ts` still uses the absolute
  `http://localhost:8000` base
- Production needs the same `/uploads` rule in whatever serves the frontend

## Upload safety

| Concern | Handling |
| --- | --- |
| Path traversal | Client filename is discarded entirely. Stored name is `uuid4().hex` + extension. |
| Type | Only `image/jpeg`, `image/png`, `image/webp`. Anything else → 422. |
| Size | 10 MB. Reads the whole body to check, so a 500 MB upload is buffered before rejection. See limitations. |
| Empty file | 422. |
| Who | Farmers only. Buyers get 403, anonymous gets 401. |

**Magic bytes are not validated.** A file whose declared content type is
`image/jpeg` but whose bytes are something else will be stored as `.jpg`.
`StaticFiles` then serves it as `image/jpeg`, which browsers will not execute
as HTML — so the practical risk is low, but the check is on the client's word.
Adding `imghdr`-style sniffing is a small follow-up.

## The lifespan lock is enforced server-side

This is the part worth reading carefully.

The form disables the `lifespan_hours` input when a farmer has
`>= REPORT_LOCK_THRESHOLD` reports, pre-filled with the category default. But a
disabled input is cosmetic — anyone can POST directly with any number.

So `create_listing` re-checks on the server:

    report_count = COUNT(reports WHERE reported_user_id = user.id)
    if report_count >= settings.report_lock_threshold:
        lifespan = category.default_lifespan_hours

It **replaces** the value rather than rejecting the request, so the form still
works and the farmer is not left staring at a 422. The endpoint returns the
stored `lifespan_hours` so the UI can report what actually happened:

> Useful life stored as 48 hours. Your account has enough reports against it
> that the lifespan is fixed to the category default.

`test_lock_cannot_be_bypassed_by_posting_directly` asserts exactly this: it
sends `lifespan_hours: 600` and checks the database holds `24`.

## Why the map uses CircleMarker, not Marker

Leaflet's default marker icon is a PNG whose URL is resolved at runtime from
the CSS/JS. Bundlers mangle those paths, so `Marker` renders as nothing under
Vite unless you re-point `L.Icon.Default` at imported assets.

`CircleMarker` is pure SVG with no asset lookup. It works with zero plumbing.
The tradeoff is a circle instead of a pin — visually plainer, functionally
identical.

The map is a **helper, not a requirement**. `location_text` is required;
coordinates are optional. A farmer who never touches the map gets `NULL`
lat/lng, which is exactly what every seeded listing has today.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **63 passed** (2 freshness + 19 order + 9 checkout + 12 reports +
12 upload + 9 listing-create).

Then in the browser:

1. Sign in as `farmer@farmlink.demo` / `Demo123!`.
2. The header now shows a **Sell** link, and the dashboard has a
   **Create listing** button. Both go to `/listings/new`.
3. Pick a category. **Useful life auto-fills** from that category's default.
4. Click the map. A green circle appears and the coordinates are shown.
   Click **Clear pin** — the circle goes.
5. Choose a JPEG. A preview appears. The image is served through the proxy at
   `http://localhost:5173/uploads/...` — confirm in DevTools that the request
   is not going to :8000 directly.
6. **Publish listing.** The confirmation reports the stored lifespan.
7. Go to `/marketplace`. Your listing is there with the uploaded photo.

Step 5 is the one that proves the proxy works.

## Known limitations

- **Whole file is buffered to check size.** `await file.read()` loads up to
  10 MB into memory before the limit is enforced. At 10 MB that is fine; at
  100 MB it would not be.
- **No magic-byte validation**, described above.
- **Uploaded files are never deleted.** Removing a listing, or replacing its
  photo, leaves the old file on disk forever. A cleanup job is its own task.
- **The map does not re-centre.** `MapContainer` reads `center` only on mount.
  Placing a pin works; clearing it leaves the view where it was. Re-centring
  would need a `useMap` child calling `setView`.
- **Tiles come from openstreetmap.org.** Offline, the map area is blank.
- **The form uses plain `useState`, not react-hook-form.** `Register.tsx` uses
  RHF + zod. This form's two most important inputs (a file and a map click)
  are not text fields, and threading them through `setValue` added ceremony
  without benefit. Validation is written directly and mirrors the backend
  constraints.
- **`bulk_available` and `organic` are stored but nothing filters on them.**
- **No edit or delete for a listing.** Only create. That is a separate
  dispatch.
