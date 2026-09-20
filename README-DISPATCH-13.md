# Dispatch #13 — Delivery, route planning, and maps

## What this archive contains

Backend:

    FarmLink/backend/app/models/entities.py                     (address + order delivery columns)
    FarmLink/backend/app/schemas/api.py                         (AddressInput coords, DeliveryStatusInput, CheckoutInput)
    FarmLink/backend/app/api/routes.py                          (delivery route, status endpoint, pickup/delivery)
    FarmLink/backend/migrations/versions/0008_delivery.py       (new)
    FarmLink/backend/tests/test_delivery.py                     (new)

Frontend:

    FarmLink/frontend/src/types/index.ts           (DeliveryMethod, DeliveryStatus, DeliveryRoute)
    FarmLink/frontend/src/lib/api.ts               (deliveryRoute, updateDeliveryStatus)
    FarmLink/frontend/src/pages/Deliveries.tsx     (new — map + route + status controls)
    FarmLink/frontend/src/pages/Profile.tsx        (LocationPicker on the address form)
    FarmLink/frontend/src/pages/Checkout.tsx       (pickup / delivery choice)
    FarmLink/frontend/src/pages/Orders.tsx         (delivery status + farmer controls)
    FarmLink/frontend/src/components/Header.tsx    (Deliveries link for farmers)
    FarmLink/frontend/src/App.tsx                  (/deliveries route)

**No CSS change and no new dependency.** `leaflet` and `react-leaflet` have been
installed since the beginning.

## How to apply

**SQLite:**

    cd E:\myApps\Project\FarmLink\backend
    del farmlink.db
    uvicorn app.main:app --reload

Delete the database — `create_all()` never alters existing tables, and this adds
two columns to `addresses` and five to `orders`.

**PostgreSQL:**

    cd E:\myApps\Project\FarmLink\App
    docker compose up -d db
    cd backend
    alembic upgrade head
    uvicorn app.main:app --reload

Then:

    cd E:\myApps\Project\FarmLink\frontend
    pnpm build
    pnpm dev

## Pickup or delivery

Every order now records `delivery_method`. The checkout page asks.

- **Pickup** — no address, no coordinates, **no delivery status at all**. There
  is nothing to track. The listing's `location_text` is where the buyer goes.
- **Delivery** — address required, coordinates optional, status starts `pending`.

Existing orders default to `pickup` via a server default. None of them recorded
a delivery intention, and pickup is the honest reading.

## Delivery status is separate from the order lifecycle

    pending → out_for_delivery → delivered
                               ↘ failed

This is **not** folded into `requested/accepted/completed`. An order can be
`accepted` while its delivery is `out_for_delivery`, and marking a delivery
`delivered` does not complete the order — the farmer still confirms that
separately. The two answer different questions.

Rules enforced server-side:

- Farmer or admin only. A buyer cannot mark their own delivery delivered.
- The order must be `accepted` first. Marking something delivered before the
  farmer agreed to it is incoherent — `test_delivery_cannot_advance_before_the_order_is_accepted`.
- Pickup orders are rejected outright with a 422, since they have no delivery.

Two automatic transitions:

- **Cancelling an order** closes its delivery as `failed` with the note
  "Order cancelled before delivery completed", so it stops appearing on the
  route.
- **Reopening an order** clears the delivery status back to null, so it can be
  re-accepted and delivered properly.

## The suggested route

`GET /farmer/deliveries` returns every accepted delivery that is not finished,
plus a visiting order.

**The origin is the farmer's most recent listing that has coordinates.** There
is no farm-location field anywhere in this project, so this is a stand-in, not
a real farm gate. If the farmer has never pinned a listing, `origin` is null,
`stops` is empty, and everything lands in `unroutable` with a note explaining
why.

**The ordering is greedy nearest-neighbour** — from the current point, always go
to the nearest unvisited stop. This is the travelling-salesman problem and a
greedy walk can be arbitrarily worse than the best route. It is offered as a
suggestion the farmer can ignore, which is why that tradeoff is acceptable.

**Distances are straight-line haversine**, not road distance. Two stops 5 km
apart as the crow flies might be 12 km by road.

Each stop carries `leg_distance_km` (from the previous stop) and
`distance_from_origin_km`.

## Nothing is silently dropped

Deliveries whose addresses were never pinned appear in `unroutable`, with their
address text intact. They cannot be placed on the map or ordered into the route,
but they are still real deliveries the farmer has to make, so they are listed
separately rather than being filtered out.

`test_deliveries_without_coordinates_are_listed_as_unroutable` asserts this.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **162 passed** (132 from before + 30 delivery).

Then in the browser:

1. Sign in as `buyer@farmlink.demo`. Go to `/profile`.
2. Add an address. **Click the map to drop a pin.** Save.
3. The address card now says "Pinned at 19.9xxx, 73.7xxx". Add a second address
   without pinning it — it says "Not pinned".
4. Sign in as `farmer@farmlink.demo`. Create a listing and **pin it on the map**.
   This becomes the route origin.
5. Sign back in as the buyer. Add something to the cart. At checkout, choose
   **Deliver to me** and the pinned address. Place the order.
6. Place a second order, this time choosing **I will collect it**.
7. Sign in as the farmer. Go to `/orders`. Accept both.
8. The delivery order shows **Start delivery**. The pickup order shows
   "Pickup from the farm" and no delivery controls.
9. Go to `/deliveries`. The pinned delivery is a stop on the map, with the route
   line from your listing pin. The pickup order is absent.
10. Click **Start delivery**, then **Mark delivered**. The stop leaves the map.

Step 8 is the one that proves pickup orders have no delivery lifecycle. Step 9
proves the route only contains what it should.

## Known limitations

- **No road distances or drive times.** Haversine only. Real routing needs OSRM
  or a paid API, neither of which is configured.
- **Nearest-neighbour is not optimal.** Described above. For 3–5 stops it is
  usually fine; for 20 it will be visibly worse than a proper solver.
- **The route origin is a hack.** "Most recent located listing" is not the farm.
  A proper fix is a farm-location field on the user profile.
- **Coordinates are optional, so many deliveries will be unroutable.** The
  seeded listings have no pins and existing addresses have none. Only what you
  pin yourself will route.
- **No live tracking.** The buyer sees the delivery status on their order but
  has no map and no position updates.
- **The buyer never sees the map.** `/deliveries` is farmer-only. A buyer cannot
  see where their delivery is.
- **No delivery time window.** No "arriving between 2 and 4pm", no scheduling.
- **`delivery_note` is only set for failures.** There is nowhere to record a
  general note about a delivery that went fine.
- **Delivered and failed deliveries leave the route entirely.** They are visible
  on `/orders` but there is no delivery history view.
- **Admin can advance a delivery but has no delivery UI.** The endpoint allows
  it; only the farmer's pages expose it.
- **`deliveries_open` counts across all farmers** in `/admin/metrics`, not per
  farmer.
- **The map does not re-centre** as stops are completed. `MapContainer` reads
  `center` only on mount.
- **Route is recomputed on every page load.** There is no saved route.
