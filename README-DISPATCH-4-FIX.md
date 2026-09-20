# Dispatch #4 — correction patch

Apply this **after** dispatch #4. Overwrite these two files:

    FarmLink/backend/app/api/routes.py
    FarmLink/backend/tests/conftest.py

## What was wrong

### 1. `capped` in the reopen response was always `false`

`reopen_order` reassigned `order.quantity` before comparing it:

    order.quantity = new_quantity
    ...
    'capped': new_quantity < order.quantity or None

After the assignment the comparison was `new_quantity < new_quantity`, always
`False`. The `or None` also meant the field could only ever be `None` or
`False`, never `True` — a caller could never tell that quantity had been
reduced.

Fixed by capturing `original_quantity` before the assignment and comparing
against that. The field is now a real boolean.

### 2. `make_listing` crashed on its second call for the same farmer

`Category.name` is `unique=True`, and the fixture named categories
`f'Cat {farmer.id}'`. Two listings for one farmer produced two identical
category names and an `IntegrityError`.

`test_cooldown_does_not_apply_to_a_different_listing` creates two listings for
one farmer, so it errored rather than passing. Category names are now numbered
by existing row count.

### 3. The SQLite setup instructions in the dispatch #4 README were wrong

That README said `create_all()` would "add the new column" to an existing
SQLite database. It does not — `create_all()` issues
`CREATE TABLE IF NOT EXISTS` and never alters existing tables. Against an
existing `backend/farmlink.db`, every order query would have failed with
`no such column: orders.status_changed_at`.

## Correct setup for your SQLite database

You chose to recreate it. Order matters:

1. **Stop uvicorn** if it is running. On Windows the file is locked while the
   server holds it, and the delete will fail.
2. Delete the database:
```

cd E:\myApps\Project\FarmLink\backend
del farmlink.db

```
3. Start the backend:
```

uvicorn app.main:app --reload

```

On startup the SQLite branch of `startup()` runs `create_all()`, which creates
all four tables *including* `status_changed_at`, then `seed()` repopulates the
demo users, categories, and six listings because `DEMO_MODE` defaults to true.

**You lose any orders you placed while testing.** Listings, users, and
categories are reseeded identically.

## Verify

 cd E:\myApps\Project\FarmLink\backend
 pytest

Expect **21 passed**. Previously this was 20 passed and 1 error, from the
`make_listing` collision.

Then confirm the column exists:

 python -c "import sqlite3; print([r[1] for r in sqlite3.connect('farmlink.db').execute('PRAGMA table_info(orders)')])"

`status_changed_at` should appear in the list.

## Remaining gap

There is still no test asserting on the `capped` field — which is exactly why
bug #1 survived. Worth adding:

 def test_reopen_reports_capping(client, db, auth, make_user, make_listing):
     farmer = make_user('farmer@test.demo', 'farmer')
     buyer_a = make_user('a@test.demo', 'buyer')
     buyer_b = make_user('b@test.demo', 'buyer')
     listing = make_listing(farmer, quantity=35)

     order_a = _place_order(client, auth, buyer_a, listing, 10).json()['id']
     _set_status(client, auth, farmer, order_a, 'rejected')
     _place_order(client, auth, buyer_b, listing, 30)

     body = client.post(f'/orders/{order_a}/reopen', headers=auth(farmer)).json()

     assert body['quantity'] == 5
     assert body['capped'] is True

Append it to `tests/test_orders.py`. `_place_order` and `_set_status` are
already defined at the top of that file.
