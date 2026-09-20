# Dispatch #14 — Demand forecasting

## What this archive contains

Backend:

    FarmLink/backend/app/api/routes.py        (GET /forecast)
    FarmLink/backend/tests/test_forecast.py   (new)

Frontend:

    FarmLink/frontend/src/types/index.ts          (Forecast, ForecastItem, ForecastTrend)
    FarmLink/frontend/src/lib/api.ts              (forecast())
    FarmLink/frontend/src/pages/Forecast.tsx      (new — full view)
    FarmLink/frontend/src/pages/Dashboard.tsx     (compact forecast section)
    FarmLink/frontend/src/components/Header.tsx   (Forecast link for farmers)
    FarmLink/frontend/src/App.tsx                 (/forecast route)

**No migration, no new table, no new dependency.** Everything derives from
orders that already exist.

## How to apply

    cd E:\myApps\Project\FarmLink\backend
    uvicorn app.main:app --reload

No database deletion this time — no schema changed.

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build
    pnpm dev

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **185 passed** (162 from before + 23 forecast).

## Read this before trusting the number

**With a handful of orders, this is close to a restatement of the raw data, not
a prediction.** A farmer with two orders gets a "forecast" that is those two
numbers averaged. The structure is right; the statistics are not meaningful
until there is real order history.

The seeded database has **zero orders**, so a fresh install shows an empty
forecast with a note explaining why. It only populates once you place orders.

`has_enough_data` is false below 3 orders in a group. The UI says so on those
rows rather than showing the number with false authority.

## What counts as demand

`requested` + `accepted` + `completed`. Every order placed counts, including
ones the farmer never answered — an unanswered request is still evidence
somebody wanted the produce.

**Excluded:** `rejected` and `cancelled`. Those represent demand that was
explicitly turned away.

## The two windows

- **8 weeks back** — orders in this range are averaged into a weekly rate
- **2 weeks forward** — that rate, multiplied by 2, is the forecast

The window is also split in half: the most recent 4 weeks against the 4 before
it. The change between them is the trend.

**Under 15% either way is called steady.** A small wobble in a 4-week window is
noise, and labelling it "rising" would be a lie dressed as a statistic.

When there is no prior demand at all, the trend is `rising` and `trend_pct` is
`null` — dividing by zero is undefined, and reporting a percentage would be
inventing one.

## Grouping

By **category + location + unit**. All three.

The unit is not decoration. Summing 10 kg and 3 dozen into "13" would produce a
figure that is not a quantity of anything. This is the same rule the
subscription cycle generator enforces, for the same reason.

Location comes from the listing's `location_text`, which is free text. "Nashik"
and "Nashik, Maharashtra" are two different groups. Normalising them would need
a location dictionary that does not exist. Blank locations group under
"Unspecified" rather than being dropped.

## Scoped to one farmer

`GET /forecast` returns the **caller's own orders**. A grower in Nashik does not
benefit from knowing what buyers want from someone else in Pune, and mixing the
two would make the number meaningless for both.

**Buyer and admin get 403.** Platform-wide demand across all farmers is a
different feature and is not built.

## Where it appears

**Farmer dashboard** — the top 3 lines, showing the **weekly rate**, because
"~25 kg per week" is more actionable than "~50 kg over the next two weeks".

**`/forecast`** — every line, with the full breakdown: 2-week projection, weekly
rate, order count, past quantity, the recent-vs-prior split, and the trend. Plus
a section explaining what the number means, because a farmer should know they
are looking at an 8-week average and not a promise.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **185 passed**.

Then in the browser, as `farmer@farmlink.demo`:

1. `/forecast` — an empty state explaining there are no orders yet.
2. Place a few orders as `buyer@farmlink.demo` against that farmer's listings.
   Give them a mix of statuses: leave some `requested`, accept one, reject one.
3. Back as the farmer, reload `/forecast`. One line per category+location+unit.
4. The rejected order's quantity is **not** in the total.
5. `/dashboard` — the same lines appear under the metrics, showing per-week
   figures.

Step 4 is the one that proves the status filter works.

## Known limitations

- **Meaningless with little data.** Described above. This is the headline
  caveat.
- **No seasonality.** A rolling 8-week average cannot know that tomato demand
  spikes in a particular month. There is not enough history for that to be
  learnable anyway.
- **Straight average, not weighted.** An order 7 weeks ago counts exactly as
  much as one yesterday. Exponential smoothing would weight recent orders
  higher; that was not the chosen approach.
- **Location is exact-string grouping.** "Nashik" and "Nashik, Maharashtra" are
  separate lines. No normalisation exists.
- **Only the farmer sees it.** No admin view, no platform-wide demand.
- **No per-buyer view.** A farmer cannot see who is likely to reorder.
- **No charts.** The `/forecast` page is text and numbers. You mentioned charts
  as a later addition; that is a separate dispatch.
- **Trend threshold is a magic number.** 15% was picked as reasonable. It is not
  derived from anything.
- **`has_enough_data` threshold is also arbitrary.** 3 orders. Below that the
  flag is false and the UI says so, but the number is still returned — the API
  does not hide it.
- **No caching.** The forecast is computed on every request. At demo scale that
  is a handful of rows; at thousands of orders it would need a materialised
  view or a scheduled job.
- **Nothing expires or is stored.** There is no forecast history, so you cannot
  compare what was predicted against what happened.
