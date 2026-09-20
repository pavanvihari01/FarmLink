"""Delivery: coordinates, pickup vs delivery, status tracking, and routing."""
from datetime import datetime, timedelta

from app.models.entities import Address, Listing, Order

def _place(client, auth, buyer, listing, quantity=5, method='delivery', address='12 Market Road, Pune', lat=19.99, lng=73.78):
    return client.post(
        '/orders',
        json={
            'listing_id': listing.id,
            'quantity': quantity,
            'delivery_method': method,
            'delivery_address': address if method == 'delivery' else None,
            'delivery_latitude': lat if method == 'delivery' else None,
            'delivery_longitude': lng if method == 'delivery' else None,
        },
        headers=auth(buyer),
    )

def _accept(client, auth, farmer, order_id):
    return client.patch(f'/orders/{order_id}/status', json={'status': 'accepted'}, headers=auth(farmer))

def _deliver(client, auth, farmer, order_id):
    """Walk a delivery from pending to delivered.

    The transition table does not allow pending -> delivered in one step, so
    the intermediate state has to be set. Tests that only care about the end
    state call this rather than repeating the pair.
    """
    client.patch(f'/orders/{order_id}/delivery-status', json={'status': 'out_for_delivery'}, headers=auth(farmer))
    return client.patch(f'/orders/{order_id}/delivery-status', json={'status': 'delivered'}, headers=auth(farmer))

# --------------------------------------------------------------------------
# Address coordinates
# --------------------------------------------------------------------------

def test_address_stores_coordinates(client, db, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')
    r = client.post(
        '/addresses',
        json={
            'label': 'Home', 'line1': '12 Market Road', 'city': 'Pune',
            'state': 'Maharashtra', 'pincode': '411001',
            'latitude': 18.5204, 'longitude': 73.8567,
        },
        headers=auth(buyer),
    )

    assert r.status_code == 200
    assert r.json()['latitude'] == 18.5204
    a = db.get(Address, r.json()['id'])
    assert a.latitude == 18.5204

def test_address_without_coordinates_is_allowed(client, db, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')
    r = client.post(
        '/addresses',
        json={'label': 'Home', 'line1': '12 Market Road', 'city': 'Pune', 'state': 'MH', 'pincode': '411001'},
        headers=auth(buyer),
    )

    # Saving an unpinned address is still fine — it just cannot be delivered to.
    assert r.status_code == 200
    assert r.json()['latitude'] is None

# --------------------------------------------------------------------------
# Pickup vs delivery
# --------------------------------------------------------------------------

def test_pickup_order_has_no_delivery_status(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place(client, auth, buyer, listing, method='pickup').json()['id']

    order = db.get(Order, order_id)
    assert order.delivery_method == 'pickup'
    assert order.delivery_status is None
    assert order.delivery_address is None
    assert order.delivery_latitude is None

def test_delivery_order_starts_pending(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place(client, auth, buyer, listing).json()['id']

    order = db.get(Order, order_id)
    assert order.delivery_method == 'delivery'
    assert order.delivery_status == 'pending'
    assert order.delivery_latitude == 19.99

def test_delivery_without_an_address_is_rejected(client, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    r = _place(client, auth, buyer, listing, address=None)

    assert r.status_code == 422

def test_checkout_carries_the_delivery_method(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    r = client.post(
        '/orders/checkout',
        json={
            'items': [{'listing_id': listing.id, 'quantity': 5}],
            'delivery_method': 'delivery',
            'delivery_address': '99 Farm Lane, Nashik',
            'delivery_latitude': 19.99,
            'delivery_longitude': 73.78,
        },
        headers=auth(buyer),
    )

    assert r.status_code == 200
    order = db.get(Order, r.json()['created'][0]['order_id'])
    assert order.delivery_method == 'delivery'
    assert order.delivery_status == 'pending'
    assert order.delivery_address == '99 Farm Lane, Nashik'

# --------------------------------------------------------------------------
# Delivery status transitions
# --------------------------------------------------------------------------

def test_farmer_can_advance_a_delivery(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)

    r = client.patch(
        f'/orders/{order_id}/delivery-status',
        json={'status': 'out_for_delivery'},
        headers=auth(farmer),
    )

    assert r.status_code == 200
    db.refresh(db.get(Order, order_id))
    assert db.get(Order, order_id).delivery_status == 'out_for_delivery'

def test_delivery_cannot_advance_before_the_order_is_accepted(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']

    r = client.patch(
        f'/orders/{order_id}/delivery-status',
        json={'status': 'delivered'},
        headers=auth(farmer),
    )

    assert r.status_code == 409

def test_pickup_order_has_no_delivery_to_advance(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing, method='pickup').json()['id']
    _accept(client, auth, farmer, order_id)

    r = client.patch(
        f'/orders/{order_id}/delivery-status',
        json={'status': 'delivered'},
        headers=auth(farmer),
    )

    assert r.status_code == 422

def test_buyer_cannot_advance_a_delivery(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)

    r = client.patch(
        f'/orders/{order_id}/delivery-status',
        json={'status': 'delivered'},
        headers=auth(buyer),
    )

    assert r.status_code == 403

def test_failed_delivery_records_the_note(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)

    client.patch(
        f'/orders/{order_id}/delivery-status',
        json={'status': 'failed', 'note': 'Nobody home'},
        headers=auth(farmer),
    )

    order = db.get(Order, order_id)
    assert order.delivery_status == 'failed'
    assert order.delivery_note == 'Nobody home'

def test_note_is_cleared_when_the_status_is_not_failed(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)
    client.patch(f'/orders/{order_id}/delivery-status', json={'status': 'failed', 'note': 'x'}, headers=auth(farmer))

    # 'failed' permits only a retry, so the next reachable status is
    # out_for_delivery — not delivered, which is two steps away.
    client.patch(f'/orders/{order_id}/delivery-status', json={'status': 'out_for_delivery'}, headers=auth(farmer))

    assert db.get(Order, order_id).delivery_note is None

def test_cancelling_an_order_closes_its_delivery(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)

    # The buyer is the cancelling party. On an accepted order a farmer may only
    # set accepted/rejected/completed — 'cancelled' is not in that set.
    r = client.patch(f'/orders/{order_id}/status', json={'status': 'cancelled'}, headers=auth(buyer))
    assert r.status_code == 200

    order = db.get(Order, order_id)
    assert order.delivery_status == 'failed'
    assert order.delivery_note is not None

def test_reopening_clears_the_delivery_status(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    # Reject straight from 'requested'. ALLOWED_TRANSITIONS gives 'accepted'
    # only completed and cancelled, so rejecting after accepting is not legal.
    client.patch(f'/orders/{order_id}/status', json={'status': 'rejected'}, headers=auth(farmer))

    # Backdate the rejection so the reopen window has passed.
    rejected = db.get(Order, order_id)
    rejected.status_changed_at = datetime.utcnow() - timedelta(days=2)
    db.commit()

    client.post(f'/orders/{order_id}/reopen', headers=auth(farmer))

    assert db.get(Order, order_id).delivery_status is None

def test_bad_delivery_status_is_rejected(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)

    r = client.patch(
        f'/orders/{order_id}/delivery-status',
        json={'status': 'teleported'},
        headers=auth(farmer),
    )

    assert r.status_code == 422

def test_pending_cannot_jump_straight_to_delivered(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)

    r = client.patch(
        f'/orders/{order_id}/delivery-status',
        json={'status': 'delivered'},
        headers=auth(farmer),
    )

    assert r.status_code == 409
    assert db.get(Order, order_id).delivery_status == 'pending'

def test_delivered_delivery_cannot_go_back_to_pending(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)
    _deliver(client, auth, farmer, order_id)

    r = client.patch(
        f'/orders/{order_id}/delivery-status',
        json={'status': 'pending'},
        headers=auth(farmer),
    )

    assert r.status_code == 409
    assert db.get(Order, order_id).delivery_status == 'delivered'

def test_failed_delivery_can_be_retried(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)
    client.patch(f'/orders/{order_id}/delivery-status', json={'status': 'failed', 'note': 'Nobody home'}, headers=auth(farmer))

    r = client.patch(
        f'/orders/{order_id}/delivery-status',
        json={'status': 'out_for_delivery'},
        headers=auth(farmer),
    )

    assert r.status_code == 200
    assert db.get(Order, order_id).delivery_status == 'out_for_delivery'
    assert db.get(Order, order_id).delivery_note is None

def test_accepting_a_reopened_delivery_order_restores_pending(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']

    # Reject while still in 'requested' — no accept first, because
    # ALLOWED_TRANSITIONS does not let an accepted order be rejected.
    client.patch(f'/orders/{order_id}/status', json={'status': 'rejected'}, headers=auth(farmer))
    rejected = db.get(Order, order_id)
    rejected.status_changed_at = datetime.utcnow() - timedelta(days=2)
    db.commit()

    client.post(f'/orders/{order_id}/reopen', headers=auth(farmer))
    assert db.get(Order, order_id).delivery_status is None

    r = _accept(client, auth, farmer, order_id)
    assert r.status_code == 200

    # The accept committed in the request's own session. Expire this session's
    # copy so the read below re-fetches rather than serving the pre-accept row.
    db.expire_all()
    assert db.get(Order, order_id).delivery_status == 'pending'

# --------------------------------------------------------------------------
# The delivery route
# --------------------------------------------------------------------------

def _delivery_at(client, auth, buyer, listing, lat, lng, farmer):
    order_id = _place(client, auth, buyer, listing, lat=lat, lng=lng).json()['id']
    _accept(client, auth, farmer, order_id)
    return order_id

def test_route_orders_stops_nearest_first(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    # The origin is the farmer's most recent located listing.
    make_listing(farmer, quantity=500, latitude=19.0, longitude=73.0)
    a = make_listing(farmer, quantity=500)
    b = make_listing(farmer, quantity=500)
    c = make_listing(farmer, quantity=500)

    near = _delivery_at(client, auth, buyer, a, 19.1, 73.0, farmer)   # ~11 km
    far = _delivery_at(client, auth, buyer, b, 19.5, 73.0, farmer)    # ~55 km
    mid = _delivery_at(client, auth, buyer, c, 19.2, 73.0, farmer)    # ~22 km

    body = client.get('/farmer/deliveries', headers=auth(farmer)).json()

    order = [s['order_id'] for s in body['stops']]
    assert order == [near, mid, far]
    assert body['total_distance_km'] > 0

def test_route_reports_the_origin(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer, quantity=500, latitude=19.0, longitude=73.0)
    listing = make_listing(farmer, quantity=500)
    _delivery_at(client, auth, buyer, listing, 19.1, 73.0, farmer)

    body = client.get('/farmer/deliveries', headers=auth(farmer)).json()

    assert body['origin']['latitude'] == 19.0
    assert body['origin']['longitude'] == 73.0

def test_each_stop_reports_distance_from_the_origin(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer, quantity=500, latitude=19.0, longitude=73.0)
    listing = make_listing(farmer, quantity=500)
    _delivery_at(client, auth, buyer, listing, 19.1, 73.0, farmer)

    body = client.get('/farmer/deliveries', headers=auth(farmer)).json()

    assert 10 < body['stops'][0]['distance_from_origin_km'] < 12

def test_deliveries_without_coordinates_are_listed_as_unroutable(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer, quantity=500, latitude=19.0, longitude=73.0)
    pinned = make_listing(farmer, quantity=500)
    unpinned = make_listing(farmer, quantity=500)
    _delivery_at(client, auth, buyer, pinned, 19.1, 73.0, farmer)

    # Written straight to the table. The API now rejects an unpinned delivery
    # order, so a row like this can only come from data created before that
    # rule, or from a subscription cycle whose stored pin is null. The
    # unroutable bucket still has to cope with it rather than dropping it.
    legacy = Order(
        buyer_id=buyer.id,
        farmer_id=farmer.id,
        listing_id=unpinned.id,
        quantity=5,
        total_amount=100.0,
        status='accepted',
        delivery_method='delivery',
        delivery_address='12 Market Road, Pune',
        delivery_status='pending',
    )
    db.add(legacy)
    db.commit()

    body = client.get('/farmer/deliveries', headers=auth(farmer)).json()

    assert len(body['stops']) == 1
    assert len(body['unroutable']) == 1
    # Nothing is silently dropped just because it has no pin.
    assert body['unroutable'][0]['address']

def test_no_origin_when_the_farmer_has_never_pinned_anything(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=500)
    _delivery_at(client, auth, buyer, listing, 19.1, 73.0, farmer)

    body = client.get('/farmer/deliveries', headers=auth(farmer)).json()

    assert body['origin'] is None
    assert body['stops'] == []
    assert len(body['unroutable']) == 1
    assert body['note']

def test_delivered_orders_leave_the_route(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer, quantity=500, latitude=19.0, longitude=73.0)
    listing = make_listing(farmer, quantity=500)
    order_id = _delivery_at(client, auth, buyer, listing, 19.1, 73.0, farmer)
    r = _deliver(client, auth, farmer, order_id)
    assert r.status_code == 200

    body = client.get('/farmer/deliveries', headers=auth(farmer)).json()

    assert body['stops'] == []

def test_unaccepted_orders_are_not_deliveries_yet(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer, quantity=500, latitude=19.0, longitude=73.0)
    listing = make_listing(farmer, quantity=500)
    # Placed but not accepted.
    _place(client, auth, buyer, listing, lat=19.1, lng=73.0)

    body = client.get('/farmer/deliveries', headers=auth(farmer)).json()

    assert body['stops'] == []
    assert body['unroutable'] == []

def test_pickup_orders_never_appear_on_the_route(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer, quantity=500, latitude=19.0, longitude=73.0)
    listing = make_listing(farmer, quantity=500)
    order_id = _place(client, auth, buyer, listing, method='pickup').json()['id']
    _accept(client, auth, farmer, order_id)

    body = client.get('/farmer/deliveries', headers=auth(farmer)).json()

    assert body['stops'] == []
    assert body['unroutable'] == []

def test_only_the_farmers_own_deliveries_are_listed(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    other = make_user('other@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer, quantity=500, latitude=19.0, longitude=73.0)
    mine = make_listing(farmer, quantity=500)
    theirs = make_listing(other, quantity=500)
    _delivery_at(client, auth, buyer, mine, 19.1, 73.0, farmer)
    _delivery_at(client, auth, buyer, theirs, 19.2, 73.0, other)

    body = client.get('/farmer/deliveries', headers=auth(farmer)).json()

    assert len(body['stops']) == 1

def test_buyer_cannot_read_the_delivery_route(client, db, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')

    r = client.get('/farmer/deliveries', headers=auth(buyer))

    assert r.status_code == 403

# --------------------------------------------------------------------------
# Dashboard and metrics
# --------------------------------------------------------------------------

def test_farmer_dashboard_counts_open_deliveries(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)

    body = client.get('/dashboard/summary', headers=auth(farmer)).json()

    assert body['open_deliveries'] == 1

def test_metrics_counts_open_deliveries(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer, quantity=35)
    order_id = _place(client, auth, buyer, listing).json()['id']
    _accept(client, auth, farmer, order_id)

    assert client.get('/admin/metrics', headers=auth(admin)).json()['deliveries_open'] == 1

    r = _deliver(client, auth, farmer, order_id)
    assert r.status_code == 200

    assert client.get('/admin/metrics', headers=auth(admin)).json()['deliveries_open'] == 0
