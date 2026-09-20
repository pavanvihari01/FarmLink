"""Batch checkout, saved addresses, and saved payment methods."""
from app.models.entities import Address, Order, PaymentMethod

def _address_payload(**over):
    payload = {
        'label': 'Home',
        'line1': '12 Market Road',
        'city': 'Pune',
        'state': 'Maharashtra',
        'pincode': '411001',
    }
    payload.update(over)
    return payload

# --------------------------------------------------------------------------
# Addresses
# --------------------------------------------------------------------------

def test_first_address_becomes_default(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    r = client.post('/addresses', json=_address_payload(), headers=auth(user))

    assert r.status_code == 200
    assert r.json()['is_default'] is True

def test_second_address_does_not_steal_default(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    client.post('/addresses', json=_address_payload(), headers=auth(user))
    r = client.post('/addresses', json=_address_payload(label='Work'), headers=auth(user))

    assert r.json()['is_default'] is False

def test_cannot_delete_another_users_address(client, db, auth, make_user):
    owner = make_user('owner@test.demo', 'buyer')
    stranger = make_user('stranger@test.demo', 'buyer')
    address_id = client.post('/addresses', json=_address_payload(), headers=auth(owner)).json()['id']

    r = client.delete(f'/addresses/{address_id}', headers=auth(stranger))

    assert r.status_code == 404
    assert db.get(Address, address_id) is not None

def test_deleting_default_promotes_another(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    first = client.post('/addresses', json=_address_payload(), headers=auth(user)).json()['id']
    client.post('/addresses', json=_address_payload(label='Work'), headers=auth(user))

    client.delete(f'/addresses/{first}', headers=auth(user))
    remaining = client.get('/addresses', headers=auth(user)).json()

    assert len(remaining) == 1
    assert remaining[0]['is_default'] is True

# --------------------------------------------------------------------------
# Payment methods
# --------------------------------------------------------------------------

def test_card_requires_last4(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    r = client.post(
        '/payment-methods',
        json={'label': 'HDFC Card', 'method_type': 'card'},
        headers=auth(user),
    )

    assert r.status_code == 422

def test_last4_must_be_four_digits(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    r = client.post(
        '/payment-methods',
        json={'label': 'HDFC Card', 'method_type': 'card', 'last4': '12'},
        headers=auth(user),
    )

    assert r.status_code == 422

def test_upi_needs_no_last4(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    r = client.post(
        '/payment-methods',
        json={'label': 'me@upi', 'method_type': 'upi'},
        headers=auth(user),
    )

    assert r.status_code == 200

# --------------------------------------------------------------------------
# Batch checkout
# --------------------------------------------------------------------------

def test_checkout_creates_one_order_per_item(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    first = make_listing(farmer, quantity=35)
    second = make_listing(farmer, quantity=35)

    r = client.post(
        '/orders/checkout',
        json={
            'items': [
                {'listing_id': first.id, 'quantity': 5},
                {'listing_id': second.id, 'quantity': 7},
            ],
            'delivery_address': '12 Market Road, Pune',
            'payment_label': 'UPI me@upi',
        },
        headers=auth(buyer),
    )

    body = r.json()
    assert r.status_code == 200
    assert len(body['created']) == 2
    assert body['failed'] == []
    db.refresh(first)
    db.refresh(second)
    assert first.available_quantity == 30
    assert second.available_quantity == 28

def test_one_bad_item_does_not_block_the_rest(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    good = make_listing(farmer, quantity=35)
    scarce = make_listing(farmer, quantity=2)

    r = client.post(
        '/orders/checkout',
        json={
            'items': [
                {'listing_id': good.id, 'quantity': 5},
                {'listing_id': scarce.id, 'quantity': 999},
            ],
            'delivery_address': '12 Market Road, Pune',
        },
        headers=auth(buyer),
    )

    body = r.json()
    assert len(body['created']) == 1
    assert len(body['failed']) == 1
    assert body['failed'][0]['listing_id'] == scarce.id
    db.refresh(good)
    db.refresh(scarce)
    assert good.available_quantity == 30
    assert scarce.available_quantity == 2

def test_checkout_snapshots_address_and_payment(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)

    r = client.post(
        '/orders/checkout',
        json={
            'items': [{'listing_id': listing.id, 'quantity': 5}],
            # Without this the method defaults to pickup, and a pickup order
            # deliberately carries no address. The pin comes with it: a
            # delivery order is rejected without one.
            'delivery_method': 'delivery',
            'delivery_address': '99 Farm Lane, Nashik',
            'delivery_latitude': 19.99,
            'delivery_longitude': 73.78,
            'payment_label': 'Card ending 4242',
        },
        headers=auth(buyer),
    )

    order = db.get(Order, r.json()['created'][0]['order_id'])
    assert order.delivery_address == '99 Farm Lane, Nashik'
    assert order.payment_label == 'Card ending 4242'

def test_checkout_requires_a_buyer(client, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    other = make_user('other@test.demo', 'farmer')
    listing = make_listing(farmer, quantity=35)

    r = client.post(
        '/orders/checkout',
        json={
            'items': [{'listing_id': listing.id, 'quantity': 5}],
            'delivery_address': '12 Market Road, Pune',
        },
        headers=auth(other),
    )

    assert r.status_code == 403

def test_checkout_rejects_empty_cart(client, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')
    r = client.post(
        '/orders/checkout',
        json={'items': [], 'delivery_address': '12 Market Road, Pune'},
        headers=auth(buyer),
    )

    assert r.status_code == 422

def test_checkout_respects_rejection_cooldown_per_item(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    blocked_listing = make_listing(farmer, quantity=35)
    other_listing = make_listing(farmer, quantity=35)

    # Get rejected on the first listing.
    order_id = client.post(
        '/orders',
        json={'listing_id': blocked_listing.id, 'quantity': 5},
        headers=auth(buyer),
    ).json()['id']
    client.patch(
        f'/orders/{order_id}/status',
        json={'status': 'rejected'},
        headers=auth(farmer),
    )

    r = client.post(
        '/orders/checkout',
        json={
            'items': [
                {'listing_id': blocked_listing.id, 'quantity': 5},
                {'listing_id': other_listing.id, 'quantity': 5},
            ],
            'delivery_address': '12 Market Road, Pune',
        },
        headers=auth(buyer),
    )

    body = r.json()
    assert len(body['created']) == 1
    assert body['created'][0]['listing_id'] == other_listing.id
    assert len(body['failed']) == 1
    assert body['failed'][0]['listing_id'] == blocked_listing.id
