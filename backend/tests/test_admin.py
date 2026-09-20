"""Admin moderation: users, listings, categories, and metrics."""
from sqlalchemy import select

from app.models.entities import Category, Listing, Order

# --------------------------------------------------------------------------
# User deactivation
# --------------------------------------------------------------------------

def test_admin_can_deactivate_a_buyer(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    buyer = make_user('buyer@test.demo', 'buyer')

    r = client.patch(f'/admin/users/{buyer.id}/active', json={'is_active': False}, headers=auth(admin))

    assert r.status_code == 200
    db.refresh(buyer)
    assert buyer.is_active is False

def test_deactivated_user_is_rejected_on_every_request(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    buyer = make_user('buyer@test.demo', 'buyer')
    token_headers = auth(buyer)

    # The token was minted while the account was active.
    client.patch(f'/admin/users/{buyer.id}/active', json={'is_active': False}, headers=auth(admin))

    r = client.get('/auth/me', headers=token_headers)

    assert r.status_code == 401

def test_deactivated_user_cannot_log_in(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    buyer = make_user('buyer@test.demo', 'buyer')
    client.patch(f'/admin/users/{buyer.id}/active', json={'is_active': False}, headers=auth(admin))

    r = client.post('/auth/login', json={'email': buyer.email, 'password': 'Demo123!'})

    assert r.status_code == 403

def test_admin_cannot_deactivate_themselves(client, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')

    r = client.patch(f'/admin/users/{admin.id}/active', json={'is_active': False}, headers=auth(admin))

    assert r.status_code == 422

def test_admin_cannot_deactivate_another_admin(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    other_admin = make_user('admin2@test.demo', 'admin')

    r = client.patch(f'/admin/users/{other_admin.id}/active', json={'is_active': False}, headers=auth(admin))

    assert r.status_code == 422
    db.refresh(other_admin)
    assert other_admin.is_active is True

def test_non_admin_cannot_deactivate_anyone(client, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')
    other = make_user('other@test.demo', 'buyer')

    r = client.patch(f'/admin/users/{other.id}/active', json={'is_active': False}, headers=auth(buyer))

    assert r.status_code == 403

# --------------------------------------------------------------------------
# Listing moderation
# --------------------------------------------------------------------------

def _set_listing(client, auth, admin, listing_id, status, **extra):
    return client.patch(
        f'/admin/listings/{listing_id}/status',
        json={'status': status, **extra},
        headers=auth(admin),
    )

def test_admin_can_suspend_a_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)

    r = _set_listing(client, auth, admin, listing.id, 'suspended', moderation_note='Pricing looks wrong')

    assert r.status_code == 200
    db.refresh(listing)
    assert listing.status == 'suspended'
    assert listing.moderation_note == 'Pricing looks wrong'

def test_suspended_listing_disappears_from_the_marketplace(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)

    _set_listing(client, auth, admin, listing.id, 'suspended')

    # /listings returns a paginated envelope, not a bare list.
    ids = [x['id'] for x in client.get('/listings').json()['items']]
    assert listing.id not in ids

def test_removed_listing_is_not_reachable_by_direct_url(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)

    _set_listing(client, auth, admin, listing.id, 'removed')

    r = client.get(f'/listings/{listing.id}')
    assert r.status_code == 404

def test_suspended_listing_cannot_be_ordered(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _set_listing(client, auth, admin, listing.id, 'suspended')

    r = client.post('/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer))

    assert r.status_code == 422

def test_removing_a_listing_with_open_orders_asks_first(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer, quantity=35)
    client.post('/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer))

    r = _set_listing(client, auth, admin, listing.id, 'removed')

    assert r.status_code == 409
    assert '1 open order' in r.json()['detail']
    db.refresh(listing)
    # Nothing changed — the admin has not confirmed yet.
    assert listing.status == 'active'

def test_confirming_removal_cancels_open_orders_and_restores_stock(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer, quantity=35)
    order_id = client.post(
        '/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer)
    ).json()['id']

    r = _set_listing(client, auth, admin, listing.id, 'removed', cancel_open_orders=True)

    assert r.status_code == 200
    assert r.json()['cancelled_orders'] == 1
    db.refresh(listing)
    db.refresh(db.get(Order, order_id))
    # 35 - 5 reserved, then restored on cancellation.
    assert listing.available_quantity == 35
    assert db.get(Order, order_id).status == 'cancelled'

def test_removal_leaves_completed_orders_untouched(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer, quantity=35)
    order_id = client.post(
        '/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer)
    ).json()['id']
    client.patch(f'/orders/{order_id}/status', json={'status': 'accepted'}, headers=auth(farmer))
    client.patch(f'/orders/{order_id}/status', json={'status': 'completed'}, headers=auth(farmer))

    r = _set_listing(client, auth, admin, listing.id, 'removed')

    # No open orders left, so removal needs no confirmation.
    assert r.status_code == 200
    assert db.get(Order, order_id).status == 'completed'

def test_admin_listing_list_reports_open_order_counts(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer, quantity=35)
    client.post('/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer))

    rows = client.get('/admin/listings', headers=auth(admin)).json()

    row = next(x for x in rows if x['id'] == listing.id)
    assert row['open_orders'] == 1

def test_bad_moderation_status_is_rejected(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)

    r = _set_listing(client, auth, admin, listing.id, 'obliterated')

    assert r.status_code == 422

def test_removed_listing_cannot_be_restored(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _set_listing(client, auth, admin, listing.id, 'removed')

    r = _set_listing(client, auth, admin, listing.id, 'active')

    assert r.status_code == 409
    db.refresh(listing)
    assert listing.status == 'removed'

def test_suspended_listing_can_still_be_restored(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _set_listing(client, auth, admin, listing.id, 'suspended')

    r = _set_listing(client, auth, admin, listing.id, 'active')

    assert r.status_code == 200
    db.refresh(listing)
    assert listing.status == 'active'

def test_deactivated_farmers_listing_cannot_be_activated(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': False}, headers=auth(admin))
    db.refresh(listing)
    # Deactivation cascaded onto the listing.
    assert listing.status == 'suspended'

    r = _set_listing(client, auth, admin, listing.id, 'active')

    assert r.status_code == 409
    db.refresh(listing)
    assert listing.status == 'suspended'

def test_reactivating_the_farmer_restores_the_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': False}, headers=auth(admin))

    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': True}, headers=auth(admin))

    db.refresh(listing)
    assert listing.status == 'active'

# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------

def test_admin_can_create_a_category(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')

    r = client.post(
        '/admin/categories',
        json={'name': 'Bitter Gourd', 'default_lifespan_hours': 120},
        headers=auth(admin),
    )

    assert r.status_code == 200
    assert db.scalar(select(Category).where(Category.name == 'Bitter Gourd')) is not None

def test_duplicate_category_name_is_rejected(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    db.add(Category(name='Tomato', default_lifespan_hours=96))
    db.commit()

    r = client.post(
        '/admin/categories',
        json={'name': 'Tomato', 'default_lifespan_hours': 48},
        headers=auth(admin),
    )

    assert r.status_code == 409

def test_admin_can_rename_a_category(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    category = Category(name='Okra', default_lifespan_hours=48)
    db.add(category)
    db.commit()

    r = client.patch(
        f'/admin/categories/{category.id}',
        json={'name': 'Lady Finger'},
        headers=auth(admin),
    )

    assert r.status_code == 200
    db.refresh(category)
    assert category.name == 'Lady Finger'

def test_rename_to_an_existing_name_is_rejected(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    db.add_all([Category(name='Tomato', default_lifespan_hours=96), Category(name='Okra', default_lifespan_hours=48)])
    db.commit()
    okra = db.query(Category).filter_by(name='Okra').one()

    r = client.patch(f'/admin/categories/{okra.id}', json={'name': 'Tomato'}, headers=auth(admin))

    assert r.status_code == 409

def test_unused_category_can_be_deleted(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    category = Category(name='Unused', default_lifespan_hours=24)
    db.add(category)
    db.commit()

    r = client.delete(f'/admin/categories/{category.id}', headers=auth(admin))

    assert r.status_code == 200
    # The delete committed in the request's session. Query instead of db.get()
    # so this session's identity map cannot serve the stale row back.
    assert db.scalar(select(Category).where(Category.id == category.id)) is None

def test_category_in_use_cannot_be_deleted(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)

    r = client.delete(f'/admin/categories/{listing.category_id}', headers=auth(admin))

    assert r.status_code == 409
    assert '1 listing' in r.json()['detail']
    assert db.get(Category, listing.category_id) is not None

def test_non_admin_cannot_manage_categories(client, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')

    r = client.post(
        '/admin/categories',
        json={'name': 'Sneaky', 'default_lifespan_hours': 24},
        headers=auth(buyer),
    )

    assert r.status_code == 403

# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def test_metrics_returns_real_counts_and_no_subscriptions(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    make_listing(farmer)

    body = client.get('/admin/metrics', headers=auth(admin)).json()

    assert body['users'] == 2
    assert body['listings'] == 1
    assert body['orders'] == 0
    # The hardcoded figure is gone — this is a real count. Nothing is
    # subscribed in this test; test_subscriptions.py covers the non-zero case.
    assert body['subscriptions'] == 0

def test_non_admin_cannot_read_metrics(client, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')

    r = client.get('/admin/metrics', headers=auth(buyer))

    assert r.status_code == 403
