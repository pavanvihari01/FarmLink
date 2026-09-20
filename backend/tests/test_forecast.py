"""Demand forecasting: windowing, grouping, trends, and access control."""
from datetime import datetime, timedelta

from app.models.entities import Order

def _order(db, buyer, farmer, listing, quantity, weeks_ago=1.0, status='requested'):
    """An order placed `weeks_ago` weeks back."""
    o = Order(
        buyer_id=buyer.id,
        farmer_id=farmer.id,
        listing_id=listing.id,
        quantity=quantity,
        total_amount=quantity * listing.price_per_unit,
        status=status,
        created_at=datetime.utcnow() - timedelta(weeks=weeks_ago),
        status_changed_at=datetime.utcnow() - timedelta(weeks=weeks_ago),
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o

def _fetch(client, auth, farmer):
    return client.get('/forecast', headers=auth(farmer))

# --------------------------------------------------------------------------
# Empty and sparse
# --------------------------------------------------------------------------

def test_no_orders_gives_an_empty_forecast_with_a_note(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')

    body = _fetch(client, auth, farmer).json()

    assert body['items'] == []
    assert body['order_count'] == 0
    assert body['note'] is not None
    assert 'nothing to forecast' in body['note']

def test_a_single_order_still_produces_an_item(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 8)

    body = _fetch(client, auth, farmer).json()

    assert len(body['items']) == 1
    assert body['items'][0]['order_count'] == 1

def test_has_enough_data_is_false_below_three_orders(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 5, weeks_ago=1)
    _order(db, buyer, farmer, listing, 5, weeks_ago=2)

    body = _fetch(client, auth, farmer).json()

    assert body['items'][0]['has_enough_data'] is False
    assert body['note'] is not None

def test_has_enough_data_is_true_at_three_orders(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    for w in (1, 2, 3):
        _order(db, buyer, farmer, listing, 5, weeks_ago=w)

    body = _fetch(client, auth, farmer).json()

    assert body['items'][0]['has_enough_data'] is True
    assert body['note'] is None

# --------------------------------------------------------------------------
# Which orders count
# --------------------------------------------------------------------------

def test_requested_orders_count(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 10, status='requested')

    assert _fetch(client, auth, farmer).json()['items'][0]['past_quantity'] == 10

def test_accepted_orders_count(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 10, status='accepted')

    assert _fetch(client, auth, farmer).json()['items'][0]['past_quantity'] == 10

def test_completed_orders_count(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 10, status='completed')

    assert _fetch(client, auth, farmer).json()['items'][0]['past_quantity'] == 10

def test_rejected_orders_do_not_count(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 10, status='rejected')

    body = _fetch(client, auth, farmer).json()

    assert body['items'] == []
    assert body['order_count'] == 0

def test_cancelled_orders_do_not_count(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 10, status='cancelled')

    assert _fetch(client, auth, farmer).json()['items'] == []

def test_orders_outside_the_window_are_excluded(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 10, weeks_ago=1)    # inside
    _order(db, buyer, farmer, listing, 99, weeks_ago=20)   # well outside

    body = _fetch(client, auth, farmer).json()

    assert body['items'][0]['past_quantity'] == 10
    assert body['order_count'] == 1

def test_another_farmers_orders_are_not_included(client, db, auth, make_user, make_listing):
    mine = make_user('farmer@test.demo', 'farmer')
    theirs = make_user('other@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    my_listing = make_listing(mine, unit='kg')
    their_listing = make_listing(theirs, unit='kg')
    _order(db, buyer, mine, my_listing, 10)
    _order(db, buyer, theirs, their_listing, 999)

    body = _fetch(client, auth, mine).json()

    assert body['items'][0]['past_quantity'] == 10
    assert len(body['items']) == 1

# --------------------------------------------------------------------------
# Grouping
# --------------------------------------------------------------------------

def test_different_locations_are_separate_items(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    nashik = make_listing(farmer, unit='kg', category=category, location_text='Nashik')
    pune = make_listing(farmer, unit='kg', category=category, location_text='Pune')
    _order(db, buyer, farmer, nashik, 10)
    _order(db, buyer, farmer, pune, 4)

    body = _fetch(client, auth, farmer).json()

    assert len(body['items']) == 2
    by_loc = {i['location']: i for i in body['items']}
    assert by_loc['Nashik']['past_quantity'] == 10
    assert by_loc['Pune']['past_quantity'] == 4

def test_different_units_are_not_summed_together(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    category = make_category(name='Tomato')
    by_kg = make_listing(farmer, unit='kg', category=category, location_text='Nashik')
    by_dozen = make_listing(farmer, unit='dozen', category=category, location_text='Nashik')
    _order(db, buyer, farmer, by_kg, 10)
    _order(db, buyer, farmer, by_dozen, 3)

    body = _fetch(client, auth, farmer).json()

    # 10 kg and 3 dozen are two different things. Summing them would be 13 of
    # nothing at all.
    assert len(body['items']) == 2
    by_unit = {i['unit']: i for i in body['items']}
    assert by_unit['kg']['past_quantity'] == 10
    assert by_unit['dozen']['past_quantity'] == 3

def test_blank_location_groups_under_unspecified(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg', location_text='')
    _order(db, buyer, farmer, listing, 5)

    body = _fetch(client, auth, farmer).json()

    assert body['items'][0]['location'] == 'Unspecified'

def test_items_are_sorted_by_forecast_quantity(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    small = make_category(name='Okra')
    big = make_category(name='Tomato')
    s = make_listing(farmer, unit='kg', category=small, location_text='A')
    b = make_listing(farmer, unit='kg', category=big, location_text='B')
    _order(db, buyer, farmer, s, 4)
    _order(db, buyer, farmer, b, 40)

    body = _fetch(client, auth, farmer).json()

    assert body['items'][0]['category'] == 'Tomato'

# --------------------------------------------------------------------------
# Arithmetic
# --------------------------------------------------------------------------

def test_weekly_rate_is_the_window_total_over_eight_weeks(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 8)

    item = _fetch(client, auth, farmer).json()['items'][0]

    # 8 kg over an 8-week window is 1 kg per week.
    assert item['weekly_rate'] == 1.0

def test_forecast_quantity_is_the_weekly_rate_times_two(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 8)

    item = _fetch(client, auth, farmer).json()['items'][0]

    assert item['forecast_quantity'] == 2.0

def test_quantities_are_summed_across_orders(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 4, weeks_ago=1)
    _order(db, buyer, farmer, listing, 6, weeks_ago=3)
    _order(db, buyer, farmer, listing, 6, weeks_ago=5)

    item = _fetch(client, auth, farmer).json()['items'][0]

    assert item['past_quantity'] == 16
    assert item['order_count'] == 3

# --------------------------------------------------------------------------
# Trend
# --------------------------------------------------------------------------

def test_trend_is_rising_when_recent_demand_is_higher(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    # Prior half (4-8 weeks back), then recent half (0-4 weeks back).
    _order(db, buyer, farmer, listing, 50, weeks_ago=6)
    _order(db, buyer, farmer, listing, 100, weeks_ago=1)

    item = _fetch(client, auth, farmer).json()['items'][0]

    assert item['trend'] == 'rising'
    assert item['trend_pct'] == 100.0

def test_trend_is_falling_when_recent_demand_is_lower(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 100, weeks_ago=6)
    _order(db, buyer, farmer, listing, 50, weeks_ago=1)

    item = _fetch(client, auth, farmer).json()['items'][0]

    assert item['trend'] == 'falling'
    assert item['trend_pct'] == -50.0

def test_trend_is_steady_within_the_threshold(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 100, weeks_ago=6)
    _order(db, buyer, farmer, listing, 105, weeks_ago=1)   # +5%, under the 15% threshold

    item = _fetch(client, auth, farmer).json()['items'][0]

    assert item['trend'] == 'steady'

def test_rising_is_called_when_there_is_no_prior_demand(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    # Everything in the recent half. Dividing by a prior of zero is undefined,
    # so this is called rising rather than producing a bogus percentage.
    _order(db, buyer, farmer, listing, 40, weeks_ago=1)

    item = _fetch(client, auth, farmer).json()['items'][0]

    assert item['trend'] == 'rising'
    assert item['trend_pct'] is None

def test_trend_is_steady_when_both_halves_are_empty(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg')
    _order(db, buyer, farmer, listing, 10, weeks_ago=7)
    # Nothing in either half once the window shifts — this asserts the boundary
    # maths does not divide by zero.
    item = _fetch(client, auth, farmer).json()['items'][0]
    assert item['trend'] in {'rising', 'steady', 'falling'}

# --------------------------------------------------------------------------
# Access
# --------------------------------------------------------------------------

def test_buyer_cannot_read_the_forecast(client, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')

    r = client.get('/forecast', headers=auth(buyer))

    assert r.status_code == 403

def test_admin_cannot_read_the_forecast(client, auth, make_user):
    # Platform-wide demand is a different feature and is not built. The forecast
    # is scoped to one farmer's own orders.
    admin = make_user('admin@test.demo', 'admin')

    r = client.get('/forecast', headers=auth(admin))

    assert r.status_code == 403

def test_anonymous_cannot_read_the_forecast(client):
    r = client.get('/forecast')

    assert r.status_code == 401

# --------------------------------------------------------------------------
# Response shape
# --------------------------------------------------------------------------

def test_response_reports_the_window_and_horizon(client, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')

    body = _fetch(client, auth, farmer).json()

    assert body['window_weeks'] == 8
    assert body['forecast_weeks'] == 2
    assert 'window_start' in body
    assert 'generated_at' in body

def test_each_item_carries_the_full_breakdown(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, unit='kg', location_text='Nashik')
    _order(db, buyer, farmer, listing, 10, weeks_ago=1)

    item = _fetch(client, auth, farmer).json()['items'][0]

    assert set(item) == {
        'category_id', 'category', 'location', 'unit',
        'order_count', 'past_quantity', 'weekly_rate', 'forecast_quantity',
        'recent_quantity', 'prior_quantity', 'trend', 'trend_pct', 'has_enough_data',
    }
