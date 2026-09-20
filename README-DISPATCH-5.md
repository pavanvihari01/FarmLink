# Dispatch #5 — Shopping flow (cart, checkout, orders, profile)

## What this archive contains

Backend:

    FarmLink/backend/app/models/entities.py                       (Address, PaymentMethod, 2 order columns)
    FarmLink/backend/app/schemas/api.py                           (4 new schemas)
    FarmLink/backend/app/api/routes.py                            (CRUD + batch checkout)
    FarmLink/backend/migrations/versions/0003_addresses_and_payment_methods.py  (new)
    FarmLink/backend/tests/test_checkout.py                       (new)

Frontend:

    FarmLink/frontend/src/context/CartContext.tsx    (new)
    FarmLink/frontend/src/pages/Cart.tsx             (new)
    FarmLink/frontend/src/pages/Checkout.tsx         (new)
    FarmLink/frontend/src/pages/Orders.tsx           (new)
    FarmLink/frontend/src/pages/Profile.tsx          (new)
    FarmLink/frontend/src/types/index.ts             (Address, PaymentMethod, Order, CheckoutResult)
    FarmLink/frontend/src/lib/api.ts                 (8 new methods)
    FarmLink/frontend/src/components/ProductCard.tsx (Add to cart)
    FarmLink/frontend/src/components/Header.tsx      (cart badge, Orders/Profile links)
    FarmLink/frontend/src/pages/Marketplace.tsx      (uses cart directly)
    FarmLink/frontend/src/App.tsx                    (CartProvider, 4 new routes)
    FarmLink/frontend/src/styles.css                 (appended a cart/order block)

## How to apply

Unzip at the project root.

**SQLite (your current setup):**

    cd E:\myApps\Project\FarmLink\backend
    del farmlink.db
    uvicorn app.main:app --reload

`create_all()` builds all six tables, then `seed()` repopulates the demo data.
Deleting is required again because `create_all()` never alters existing tables
and `orders` needs two new columns.

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

## The checkout atomicity problem, and what best-effort means

`Order` is one row per listing. A cart of 5 items becomes 5 orders. You chose
best-effort, so `POST /orders/checkout` validates and commits each item
independently:

    {
      "created": [ {"listing_id": 4, "order_id": 11, "title": "...", "quantity": 5, "total_amount": 230} ],
      "failed":  [ {"listing_id": 9, "reason": "Only 2 kg left"} ]
    }

**3 items can succeed while 2 fail, and the buyer is committed to the 3.**
That is the direct consequence of best-effort. The checkout page surfaces it
honestly: after placing, it shows "3 succeeded, 2 could not be placed" and
lists each failure reason. Only the succeeded items are removed from the cart;
the failures stay so the buyer can retry or delete them.

If you later want all-or-nothing, the change is confined to the loop in
`checkout()` — commit once at the end instead of per item.

## Cart

Client-side, `localStorage` under `farmlink.cart`. No table, no endpoints.
Lost if the buyer switches devices or clears storage. Stored via
`CartContext`, which wraps the app in `App.tsx` because `Header` (badge) and
`Marketplace` (add) both need it.

Each cart line stores a **snapshot** of the listing — title, price, unit,
image, farmer name, and the `available_quantity` at the time it was added.

**Consequence:** if a farmer changes the price after the buyer adds to cart,
the cart shows the old price but the order is created at the **current** price
(`x.price_per_unit` on the server). The confirmation screen shows what was
actually charged. To close that gap properly, the checkout page should re-fetch
listings before rendering the total — not done here.

`available_quantity` in the cart is also a snapshot. If stock drops below the
cart quantity, checkout fails for that item with "Only N kg left", which is
the correct outcome.

## Addresses and payment methods

Two new tables, both scoped to `user_id`. A user can only read, create, and
delete their own — verified by test.

The first address or payment method a user saves automatically becomes their
default. Deleting the default promotes the oldest remaining one, so a user is
never left without a default while they still have at least one.

Payment methods store a label, a `method_type` (`upi` / `card` / `cod`), and a
fake `last4` for cards. **No card numbers, no expiry, no CVV, no gateway.**
Card methods are rejected without a 4-digit `last4`.

## Order snapshots

`orders.delivery_address` (Text) and `orders.payment_label` (String) are
**text snapshots, not foreign keys**. Deleting an address later must not
rewrite the history of orders already delivered to it. This is why the
columns hold formatted strings rather than an `address_id`.

## Backward compatibility

`POST /orders` is unchanged in behaviour. `OrderCreate` gained two *optional*
fields (`delivery_address`, `payment_label`), so the 21 existing tests in
`test_orders.py` and `test_freshness.py` still pass untouched. The batch
endpoint is additive.

## Verify

    cd E:\myApps\Project\FarmLink\backend
    pytest

Expect **30 passed** (2 freshness + 19 order lifecycle + 9 checkout).

Then in the browser, as `buyer@farmlink.demo` / `Demo123!`:

1. `/marketplace` — click **Add to cart** on two different listings.
2. The header cart badge shows **2**.
3. `/cart` — change a quantity, confirm the line total updates.
4. **Proceed to checkout** without an address → the page says you have none
   and links to `/profile`.
5. `/profile` — add an address and a UPI payment method. Both should appear
   immediately, the address marked **Default**.
6. Back to `/checkout` — both selectors are populated and pre-selected.
7. **Place order** → confirmation shows N orders created.
8. `/orders` — both orders listed as `requested`. The **Cancel order** button
   appears on each.
9. Cancel one → it moves to the **Cancelled** tab.
10. Back on `/marketplace`, the listing you ordered should show a **lower
    "ready" quantity** than before.

Step 10 is the one that proves stock reservation survived the frontend
rewrite.

## Known limitations

- **Price staleness in the cart.** Described above. The cart can show a total
  that differs from what is charged.
- **No address editing.** Delete and re-add only. Editing needs a `PATCH`
  endpoint.
- **No "set as default" button.** The first one saved wins; promoting a
  different address means deleting and re-adding.
- **`GET /orders` for a farmer is wired but unused by any page yet.** The
  Orders page renders for both roles but farmer-specific actions (accept,
  reject, complete, reopen) are dispatch #6. A farmer currently sees a
  read-only list.
- **The listing link on an order goes to `/marketplace`**, not to the specific
  listing. There is no `/listings/:id` route yet.
- **Cart is per-browser.** Two tabs share it via `localStorage` but do not
  live-sync without a `storage` event listener.
- **Best-effort partial checkout**, as described.
