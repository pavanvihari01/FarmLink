# Dispatch #8 — correction

Overwrite these two files from dispatch #8:

    FarmLink/backend/app/schemas/api.py
    FarmLink/frontend/src/components/LocationPicker.tsx

Nothing else changes. Apply after #8.

## Bug 1 — coordinates were silently discarded

`ListingCreate` was missing `latitude` and `longitude`:

    class ListingCreate(BaseModel):
        category_id: int
        ...
        location_text: str
        image_url: str = '/images/market-harvest.png'
        # latitude and longitude absent

The `Listing` model has those columns, `CreateListingPayload` on the frontend
sends them, and `test_coordinates_are_stored_when_supplied` asserts they
persist — but the schema did not declare them.

Pydantic v2 defaults to `extra='ignore'`. Unknown keys are dropped without
error. So:

- `test_coordinates_are_stored_when_supplied` fails with
  `None == 19.9975`
- In the browser, the map pin appears to work, the listing saves, and the
  coordinates are gone. No error is shown at any point.

Both fields are now declared as `float | None = None`.

`test_farmer_can_create_a_listing` and the other listing tests are unaffected:
the fields default to `None`, and the columns are nullable.

## Risk 2 — aliased narrowing in the map component

Was:

    const hasPin = lat !== null && lng !== null;
    ...
    {hasPin && <CircleMarker center={[lat, lng]} />}
    {hasPin ? `Pinned at ${lat.toFixed(4)}...` : '...'}

TypeScript 4.4+ narrows through aliased conditions, so this may well have
compiled. But a compound `&&` alias consumed inside JSX is the least reliable
corner of that feature, and the failure mode is a build error rather than a
runtime one — so it is cheap to remove the doubt.

Now each usage narrows directly:

    {lat !== null && lng !== null && <CircleMarker center={[lat, lng]} />}

Same behavior, no reliance on alias tracking.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest tests/test_listing_create.py

Expect **9 passed**. Before this fix, `test_coordinates_are_stored_when_supplied`
would have failed.

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build

Expect zero TypeScript errors.

Then in the browser: create a listing with a map pin, save it, and confirm the
coordinate text appears on `/marketplace` for that listing. Or check the
database directly:

    python -c "import sqlite3; print(list(sqlite3.connect('farmlink.db').execute('SELECT id, latitude, longitude FROM listings ORDER BY id DESC LIMIT 3')))"

A non-null latitude on your newest listing is the proof.

## Still unfixed from #8, deliberately

The limitations listed in `README-DISPATCH-8.md` are unchanged. The most
worth-knowing:

- The whole upload is buffered in memory before the size limit is applied.
- Uploaded files are never deleted when a listing is removed.
- Magic bytes are not validated — the check trusts the declared content type.
- The map does not re-centre after a pin is cleared.
