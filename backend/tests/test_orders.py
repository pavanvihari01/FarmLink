"""Order lifecycle: stock reservation, transitions, reopen, cooldown."""
from datetime import datetime, timedelta

from app.models.entities import Listing, Order

def _place_order(client, auth, buyer, listing, quantity):
    return client.post(
        '/orders',
        json={'listing_id': listing.id, 'quantity': quantity},
        headers=auth(buyer),
    )

def _set_status(client, auth, user, order_id, status):
    return client.patch(
        f'/orders/{order_id}/status',
        json={'status': status},
        headers=auth(user),
    )

# --------------------------------------------------------------------------
# Stock reservation
# --------------------------------------------------------------------------

def test_order_reserves_stock_immediately(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    r = _place_order(client, auth, buyer, listing, 10)

    assert r.status_code == 200
    db.refresh(listing)
    assert listing.available_quantity == 25

def test_order_beyond_available_stock_is_rejected(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=5)

    r = _place_order(client, auth, buyer, listing, 10)

    assert r.status_code == 422
    db.refresh(listing)
    assert listing.available_quantity == 5

def test_rejection_restores_stock(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer, listing, 10).json()['id']
    r = _set_status(client, auth, farmer, order_id, 'rejected')

    assert r.status_code == 200
    db.refresh(listing)
    assert listing.available_quantity == 35

def test_cancellation_restores_stock(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer, listing, 10).json()['id']
    r = _set_status(client, auth, buyer, order_id, 'cancelled')

    assert r.status_code == 200
    db.refresh(listing)
    assert listing.available_quantity == 35

def test_completion_consumes_stock(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer, listing, 10).json()['id']
    _set_status(client, auth, farmer, order_id, 'accepted')
    r = _set_status(client, auth, farmer, order_id, 'completed')

    assert r.status_code == 200
    db.refresh(listing)
    # Stock left at 25 — completing does not return it.
    assert listing.available_quantity == 25

# --------------------------------------------------------------------------
# Transition legality
# --------------------------------------------------------------------------

def test_buyer_cannot_accept_own_order(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    r = _set_status(client, auth, buyer, order_id, 'accepted')

    assert r.status_code == 403

def test_stranger_cannot_touch_order(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    stranger = make_user('stranger@test.demo', 'farmer')
    listing = make_listing(farmer)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    r = _set_status(client, auth, stranger, order_id, 'accepted')

    assert r.status_code == 403

def test_cannot_transition_a_terminal_order(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'rejected')
    r = _set_status(client, auth, farmer, order_id, 'accepted')

    assert r.status_code == 409

def test_cannot_skip_from_requested_to_completed(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    r = _set_status(client, auth, farmer, order_id, 'completed')

    assert r.status_code == 409

def test_admin_can_complete_an_accepted_order(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'accepted')
    r = _set_status(client, auth, admin, order_id, 'completed')

    assert r.status_code == 200

# --------------------------------------------------------------------------
# Reopen
# --------------------------------------------------------------------------

def test_reopen_caps_quantity_to_remaining_stock(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer_a = make_user('a@test.demo', 'buyer')
    buyer_b = make_user('b@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    # A orders 10, gets rejected, stock returns to 35.
    order_a = _place_order(client, auth, buyer_a, listing, 10).json()['id']
    _set_status(client, auth, farmer, order_a, 'rejected')

    # Backdate the rejection so the reopen window has passed.
    rejected = db.get(Order, order_a)
    rejected.status_changed_at = datetime.utcnow() - timedelta(days=2)
    db.commit()

    # B takes 30, leaving 5.
    _place_order(client, auth, buyer_b, listing, 30)

    r = client.post(f'/orders/{order_a}/reopen', headers=auth(farmer))

    assert r.status_code == 200
    assert r.json()['quantity'] == 5
    db.refresh(listing)
    assert listing.available_quantity == 0

def test_reopen_fails_when_no_stock_left(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer_a = make_user('a@test.demo', 'buyer')
    buyer_b = make_user('b@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_a = _place_order(client, auth, buyer_a, listing, 10).json()['id']
    _set_status(client, auth, farmer, order_a, 'rejected')

    # Backdate the rejection so the reopen window has passed.
    rejected = db.get(Order, order_a)
    rejected.status_changed_at = datetime.utcnow() - timedelta(days=2)
    db.commit()

    _place_order(client, auth, buyer_b, listing, 35)

    r = client.post(f'/orders/{order_a}/reopen', headers=auth(farmer))

    assert r.status_code == 409
    db.refresh(listing)
    assert listing.available_quantity == 0

def test_completed_order_cannot_be_reopened(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'accepted')
    _set_status(client, auth, farmer, order_id, 'completed')

    r = client.post(f'/orders/{order_id}/reopen', headers=auth(farmer))

    assert r.status_code == 409

def test_buyer_cannot_reopen(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'rejected')

    r = client.post(f'/orders/{order_id}/reopen', headers=auth(buyer))

    assert r.status_code == 403

def test_reopen_is_blocked_inside_the_window(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'rejected')

    r = client.post(f'/orders/{order_id}/reopen', headers=auth(farmer))

    assert r.status_code == 409
    assert db.get(Order, order_id).status == 'rejected'

def test_reopen_is_allowed_after_the_window(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'rejected')

    rejected = db.get(Order, order_id)
    rejected.status_changed_at = datetime.utcnow() - timedelta(days=2)
    db.commit()

    r = client.post(f'/orders/{order_id}/reopen', headers=auth(farmer))

    assert r.status_code == 200
    assert db.get(Order, order_id).status == 'requested'

def test_delivery_order_cannot_be_completed_before_delivered(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = client.post(
        '/orders',
        json={
            'listing_id': listing.id,
            'quantity': 5,
            'delivery_method': 'delivery',
            'delivery_address': '12 Market Road, Pune',
            # A delivery order is rejected without a pin, so the payload has
            # to carry one or the response has no 'id' to read.
            'delivery_latitude': 19.99,
            'delivery_longitude': 73.78,
        },
        headers=auth(buyer),
    ).json()['id']
    _set_status(client, auth, farmer, order_id, 'accepted')

    r = _set_status(client, auth, farmer, order_id, 'completed')

    assert r.status_code == 409
    assert db.get(Order, order_id).status == 'accepted'

def test_delivery_order_can_be_completed_once_delivered(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = client.post(
        '/orders',
        json={
            'listing_id': listing.id,
            'quantity': 5,
            'delivery_method': 'delivery',
            'delivery_address': '12 Market Road, Pune',
            # A delivery order is rejected without a pin, so the payload has
            # to carry one or the response has no 'id' to read.
            'delivery_latitude': 19.99,
            'delivery_longitude': 73.78,
        },
        headers=auth(buyer),
    ).json()['id']
    _set_status(client, auth, farmer, order_id, 'accepted')
    # The delivery has to be walked through out_for_delivery; pending ->
    # delivered in one step is not in the transition table.
    client.patch(f'/orders/{order_id}/delivery-status', json={'status': 'out_for_delivery'}, headers=auth(farmer))
    client.patch(f'/orders/{order_id}/delivery-status', json={'status': 'delivered'}, headers=auth(farmer))

    r = _set_status(client, auth, farmer, order_id, 'completed')

    assert r.status_code == 200
    assert db.get(Order, order_id).status == 'completed'

# --------------------------------------------------------------------------
# Buyer rejection cooldown
# --------------------------------------------------------------------------

def test_rejected_buyer_is_blocked_from_reordering_same_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'rejected')

    r = _place_order(client, auth, buyer, listing, 5)

    assert r.status_code == 429

def test_cooldown_does_not_apply_to_a_different_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    first = make_listing(farmer, quantity=35)
    second = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer, first, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'rejected')

    r = _place_order(client, auth, buyer, second, 5)

    assert r.status_code == 200

def test_cooldown_expires(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'rejected')

    # Backdate the rejection past the 48-hour window.
    order = db.get(Order, order_id)
    order.status_changed_at = datetime.utcnow() - timedelta(hours=49)
    db.commit()

    r = _place_order(client, auth, buyer, listing, 5)

    assert r.status_code == 200

def test_cancellation_does_not_trigger_cooldown(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer, listing, 5).json()['id']
    _set_status(client, auth, buyer, order_id, 'cancelled')

    r = _place_order(client, auth, buyer, listing, 5)

    assert r.status_code == 200

def test_cooldown_does_not_affect_other_buyers(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer_a = make_user('a@test.demo', 'buyer')
    buyer_b = make_user('b@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    order_id = _place_order(client, auth, buyer_a, listing, 5).json()['id']
    _set_status(client, auth, farmer, order_id, 'rejected')

    r = _place_order(client, auth, buyer_b, listing, 5)

    assert r.status_code == 200
