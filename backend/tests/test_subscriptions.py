"""Subscriptions: creation, lazy cycle generation, skipping, and cancellation."""
from datetime import datetime, timedelta

from app.models.entities import Listing, Order, Subscription, SubscriptionCycle

# A pinned address. Every subscription is a delivery, and a delivery needs a
# destination the farmer can route to — an unpinned one has no fulfilment path.
PIN_LAT = 18.5204
PIN_LNG = 73.8567

def _create(client, auth, buyer, farmer, category, **over):
    body = {
        'farmer_id': farmer.id,
        'category_id': category.id,
        'quantity': 5,
        'unit': 'kg',
        'frequency_days': 7,
        'delivery_address': '12 Market Road, Pune',
        'delivery_latitude': PIN_LAT,
        'delivery_longitude': PIN_LNG,
        'payment_label': 'UPI me@upi',
    }
    body.update(over)
    return client.post('/subscriptions', json=body, headers=auth(buyer))

def _backdate(db, sub, hours):
    """Push a subscription's next cycle into the past so it is due."""
    sub.next_cycle_at = datetime.utcnow() - timedelta(hours=hours)
    db.commit()

# --------------------------------------------------------------------------
# Creation
# --------------------------------------------------------------------------

def test_buyer_can_subscribe_to_a_farmer_and_category(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')

    r = _create(client, auth, buyer, farmer, category)

    assert r.status_code == 200
    sub = db.get(Subscription, r.json()['id'])
    assert sub.buyer_id == buyer.id
    assert sub.farmer_id == farmer.id
    assert sub.category_id == category.id
    assert sub.status == 'active'

def test_first_cycle_is_one_frequency_away(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()

    r = _create(client, auth, buyer, farmer, category, frequency_days=7)

    sub = db.get(Subscription, r.json()['id'])
    # A "weekly box" that arrives the moment you subscribe would be a surprise.
    delta = sub.next_cycle_at - datetime.utcnow()
    assert timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1)

def test_subscription_stores_the_delivery_coordinates(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()

    sub_id = _create(client, auth, buyer, farmer, category).json()['id']

    sub = db.get(Subscription, sub_id)
    assert sub.delivery_latitude == PIN_LAT
    assert sub.delivery_longitude == PIN_LNG

def test_subscription_without_a_pin_is_rejected(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()

    # Overriding to None: the helper's defaults are pinned, so this is the
    # only way to express "no pin".
    r = _create(client, auth, buyer, farmer, category, delivery_latitude=None, delivery_longitude=None)

    assert r.status_code == 422
    assert 'pin' in r.json()['detail'].lower()
    assert db.query(Subscription).count() == 0

def test_a_half_pin_is_not_enough(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()

    r = _create(client, auth, buyer, farmer, category, delivery_longitude=None)

    assert r.status_code == 422
    assert db.query(Subscription).count() == 0

def test_farmer_cannot_create_a_subscription(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    other = make_user('other@test.demo', 'farmer')
    category = make_category()

    r = _create(client, auth, farmer, other, category)

    assert r.status_code == 403

def test_cannot_subscribe_to_yourself(client, db, auth, make_user, make_category):
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()

    r = _create(client, auth, buyer, buyer, category)

    # A buyer is not a farmer, so this fails the role check first.
    assert r.status_code == 404

def test_cannot_subscribe_to_a_deactivated_farmer(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()
    farmer.is_active = False
    db.commit()

    r = _create(client, auth, buyer, farmer, category)

    assert r.status_code == 422

def test_unknown_category_is_rejected(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')

    r = client.post(
        '/subscriptions',
        json={
            'farmer_id': farmer.id,
            'category_id': 9999,
            'quantity': 5,
            'unit': 'kg',
            'frequency_days': 7,
            'delivery_address': '12 Market Road, Pune',
            'delivery_latitude': PIN_LAT,
            'delivery_longitude': PIN_LNG,
        },
        headers=auth(buyer),
    )

    assert r.status_code == 404

def test_odd_frequency_is_rejected(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()

    r = _create(client, auth, buyer, farmer, category, frequency_days=3)

    assert r.status_code == 422

# --------------------------------------------------------------------------
# Cycle generation
# --------------------------------------------------------------------------

def test_no_cycles_generated_before_the_first_is_due(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()
    _create(client, auth, buyer, farmer, category)

    body = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    assert body['generated'] == 0
    assert db.query(SubscriptionCycle).count() == 0

def test_due_cycle_creates_an_order(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    listing = make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category, quantity=5).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    body = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    assert body['generated'] == 1
    assert body['skipped'] == 0
    db.refresh(listing)
    assert listing.available_quantity == 30
    order = db.query(Order).one()
    assert order.subscription_id == sub_id
    assert order.buyer_id == buyer.id
    assert order.quantity == 5
    assert order.status == 'requested'

def test_generated_order_is_a_routable_delivery(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    client.post('/subscriptions/generate-due', headers=auth(buyer))

    # The subscription says "delivering to", so the order it produces must be a
    # delivery — and one the farmer can actually route and complete.
    order = db.query(Order).one()
    assert order.delivery_method == 'delivery'
    assert order.delivery_status == 'pending'
    assert order.delivery_latitude == PIN_LAT
    assert order.delivery_longitude == PIN_LNG

def test_order_snapshots_the_subscription_address(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(
        client, auth, buyer, farmer, category,
        delivery_address='99 Farm Lane, Nashik', payment_label='Card ending 4242',
    ).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    client.post('/subscriptions/generate-due', headers=auth(buyer))

    order = db.query(Order).one()
    assert order.delivery_address == '99 Farm Lane, Nashik'
    assert order.payment_label == 'Card ending 4242'

def test_next_cycle_advances_by_the_frequency(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category, frequency_days=14).json()['id']
    sub = db.get(Subscription, sub_id)
    _backdate(db, sub, 1)
    was = sub.next_cycle_at

    client.post('/subscriptions/generate-due', headers=auth(buyer))

    db.refresh(sub)
    assert abs((sub.next_cycle_at - (was + timedelta(days=14))).total_seconds()) < 5

def test_generation_is_idempotent(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    first = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()
    second = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    assert first['generated'] == 1
    assert second['generated'] == 0
    assert db.query(Order).count() == 1

def test_cycle_is_skipped_when_the_farmer_has_no_stock(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    # No listing at all in this category.
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    body = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    assert body['generated'] == 0
    assert body['skipped'] == 1
    cycle = db.query(SubscriptionCycle).one()
    assert cycle.status == 'skipped'
    assert 'Tomato' in cycle.reason
    assert db.query(Order).count() == 0

def test_cycle_is_skipped_when_stock_is_short(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=2, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category, quantity=5).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    body = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    assert body['skipped'] == 1
    assert db.query(Order).count() == 0

def test_cycle_is_skipped_when_the_listing_is_expired(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category, lifespan_hours=24, age_hours=48)
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    body = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    assert body['skipped'] == 1

def test_cycle_is_skipped_when_the_unit_does_not_match(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    # Listed per dozen, subscribed per kg. Silently ordering five dozen would be
    # a very different thing from five kilos.
    make_listing(farmer, quantity=35, unit='dozen', category=category)
    sub_id = _create(client, auth, buyer, farmer, category, quantity=5, unit='kg').json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    body = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    assert body['skipped'] == 1

def test_a_legacy_unpinned_subscription_skips_rather_than_strands(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']

    # Written straight to the table. The API now rejects an unpinned
    # subscription, so a row like this can only predate that rule. Generating
    # an order from it would produce a delivery the farmer can never finish,
    # so the cycle is recorded as skipped instead.
    sub = db.get(Subscription, sub_id)
    sub.delivery_latitude = None
    sub.delivery_longitude = None
    _backdate(db, sub, 1)

    body = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    assert body['generated'] == 0
    assert body['skipped'] == 1
    assert db.query(Order).count() == 0
    cycle = db.query(SubscriptionCycle).one()
    assert 'pin' in cycle.reason.lower()

def test_a_legacy_unpinned_subscription_still_advances(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category, frequency_days=7).json()['id']
    sub = db.get(Subscription, sub_id)
    sub.delivery_latitude = None
    sub.delivery_longitude = None
    _backdate(db, sub, 1)
    was = sub.next_cycle_at

    client.post('/subscriptions/generate-due', headers=auth(buyer))

    db.refresh(sub)
    # A skipped cycle still moves the clock, or the subscription would retry
    # the same broken date forever.
    assert abs((sub.next_cycle_at - (was + timedelta(days=7))).total_seconds()) < 5

def test_skipped_cycle_still_advances_the_next_date(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    sub_id = _create(client, auth, buyer, farmer, category, frequency_days=7).json()['id']
    sub = db.get(Subscription, sub_id)
    _backdate(db, sub, 1)
    was = sub.next_cycle_at

    client.post('/subscriptions/generate-due', headers=auth(buyer))

    db.refresh(sub)
    assert abs((sub.next_cycle_at - (was + timedelta(days=7))).total_seconds()) < 5

def test_a_long_absence_does_not_pile_up_orders(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=500, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category, quantity=5, frequency_days=7).json()['id']
    # Ten weeks behind.
    _backdate(db, db.get(Subscription, sub_id), 24 * 70)

    body = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    # Only the most recent cycle is fulfilled. The older ones are recorded as
    # missed, because whatever was fresh ten weeks ago is long gone.
    assert body['generated'] == 1
    assert body['skipped'] >= 9
    assert db.query(Order).count() == 1
    missed = db.query(SubscriptionCycle).filter_by(status='skipped').all()
    assert any('Missed' in (c.reason or '') for c in missed)

def test_farmer_sees_generation_for_subscriptions_coming_to_them(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    # The buyer never opens their page. The farmer's visit is what triggers it.
    body = client.post('/subscriptions/generate-due', headers=auth(farmer)).json()

    assert body['generated'] == 1

# --------------------------------------------------------------------------
# Listing
# --------------------------------------------------------------------------

def test_buyer_sees_only_their_own_subscriptions(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer_a = make_user('a@test.demo', 'buyer')
    buyer_b = make_user('b@test.demo', 'buyer')
    category = make_category()
    _create(client, auth, buyer_a, farmer, category)
    _create(client, auth, buyer_b, farmer, category)

    rows = client.get('/subscriptions', headers=auth(buyer_a)).json()

    assert len(rows) == 1
    assert rows[0]['buyer_name'] == buyer_a.name

def test_farmer_sees_subscriptions_addressed_to_them(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    other = make_user('other@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()
    _create(client, auth, buyer, farmer, category)
    _create(client, auth, buyer, other, category)

    rows = client.get('/subscriptions', headers=auth(farmer)).json()

    assert len(rows) == 1
    assert rows[0]['farmer_id'] == farmer.id

def test_list_exposes_the_delivery_coordinates(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()
    _create(client, auth, buyer, farmer, category)

    rows = client.get('/subscriptions', headers=auth(buyer)).json()

    assert rows[0]['delivery_latitude'] == PIN_LAT
    assert rows[0]['delivery_longitude'] == PIN_LNG

def test_list_includes_recent_cycles(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)
    client.post('/subscriptions/generate-due', headers=auth(buyer))

    rows = client.get('/subscriptions', headers=auth(buyer)).json()

    assert len(rows[0]['recent_cycles']) == 1
    assert rows[0]['recent_cycles'][0]['status'] == 'generated'

def test_list_does_not_generate_cycles(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)

    client.get('/subscriptions', headers=auth(buyer))

    # Generation is a write, so it lives behind its own POST.
    assert db.query(Order).count() == 0

# --------------------------------------------------------------------------
# Cancellation
# --------------------------------------------------------------------------

def test_admin_can_cancel_a_subscription(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    category = make_category()
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']

    r = client.delete(f'/admin/subscriptions/{sub_id}', headers=auth(admin))

    assert r.status_code == 200
    db.refresh(db.get(Subscription, sub_id))
    assert db.get(Subscription, sub_id).status == 'cancelled'

def test_buyer_cannot_cancel_their_own_subscription(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category()
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']

    r = client.delete(f'/admin/subscriptions/{sub_id}', headers=auth(buyer))

    assert r.status_code == 403
    assert db.get(Subscription, sub_id).status == 'active'

def test_cancelled_subscription_stops_generating(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    category = make_category(name='Tomato')
    make_listing(farmer, quantity=35, unit='kg', category=category)
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']
    _backdate(db, db.get(Subscription, sub_id), 1)
    client.delete(f'/admin/subscriptions/{sub_id}', headers=auth(admin))

    body = client.post('/subscriptions/generate-due', headers=auth(buyer)).json()

    assert body['generated'] == 0
    assert db.query(Order).count() == 0

def test_cancelling_twice_is_rejected(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    category = make_category()
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']

    client.delete(f'/admin/subscriptions/{sub_id}', headers=auth(admin))
    r = client.delete(f'/admin/subscriptions/{sub_id}', headers=auth(admin))

    assert r.status_code == 409

# --------------------------------------------------------------------------
# Farmers endpoint and metrics
# --------------------------------------------------------------------------

def test_farmers_endpoint_lists_active_farmers(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer', name='Anita Verma')
    gone = make_user('gone@test.demo', 'farmer')
    make_user('buyer@test.demo', 'buyer')
    gone.is_active = False
    db.commit()

    rows = client.get('/farmers').json()

    names = [r['name'] for r in rows]
    assert 'Anita Verma' in names
    # Buyers are not farmers, and deactivated farmers are not offered.
    assert len(rows) == 1

def test_metrics_counts_active_subscriptions(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    category = make_category()
    sub_id = _create(client, auth, buyer, farmer, category).json()['id']

    assert client.get('/admin/metrics', headers=auth(admin)).json()['subscriptions'] == 1

    client.delete(f'/admin/subscriptions/{sub_id}', headers=auth(admin))

    # Cancelled subscriptions are not counted.
    assert client.get('/admin/metrics', headers=auth(admin)).json()['subscriptions'] == 0
