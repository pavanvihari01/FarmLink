"""What /recommendations/listings puts first, and why.

The endpoint used to sort by remaining freshness, which made "Recommended for
You" mean "the newest four listings". It now ranks on the buyer's own order
history, with freshness as the fallback for anyone who has none.

Each result carries a `reason` naming the strongest signal behind it, so the
UI can say why a listing was picked rather than repeating one hardcoded line.
"""
from app.models.entities import Order

def _order(db, buyer, farmer, listing, status='completed', quantity=1):
    """A historical order, written straight to the table.

    Going through the API would need stock to move and a farmer to accept; the
    endpoint under test reads order rows, not how they were created.
    """
    o = Order(
        buyer_id=buyer.id,
        farmer_id=farmer.id,
        listing_id=listing.id,
        quantity=quantity,
        total_amount=quantity * listing.price_per_unit,
        status=status,
    )
    db.add(o)
    db.commit()
    return o

# --------------------------------------------------------------------------
# With no history
# --------------------------------------------------------------------------

def test_falls_back_to_freshness_without_history(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    older = make_listing(farmer, lifespan_hours=96, age_hours=60)
    newer = make_listing(farmer, lifespan_hours=96, age_hours=5)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert [r['id'] for r in rows] == [newer.id, older.id]

def test_reason_falls_back_when_there_is_no_history(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert rows[0]['reason'] == 'Fresh today'

# --------------------------------------------------------------------------
# Category affinity
# --------------------------------------------------------------------------

def test_an_ordered_category_outranks_a_fresher_listing(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    tomatoes = make_category(name='Tomato', lifespan_hours=96)
    spinach = make_category(name='Spinach', lifespan_hours=96)
    # The order that establishes the preference. Its listing is expired, so it
    # cannot reappear in the results and muddy the comparison.
    past = make_listing(farmer, category=tomatoes, lifespan_hours=24, age_hours=48)
    _order(db, buyer, farmer, past)
    make_listing(farmer, category=spinach, lifespan_hours=96, age_hours=1)
    staler_match = make_listing(farmer, category=tomatoes, lifespan_hours=96, age_hours=70)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert rows[0]['id'] == staler_match.id

def test_reason_names_the_category(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    tomatoes = make_category(name='Tomato')
    past = make_listing(farmer, category=tomatoes, lifespan_hours=24, age_hours=48)
    _order(db, buyer, farmer, past)
    make_listing(farmer, category=tomatoes)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert rows[0]['reason'] == 'You have ordered Tomato 1 time before'

def test_reason_pluralises_the_order_count(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    tomatoes = make_category(name='Tomato')
    past = make_listing(farmer, category=tomatoes, lifespan_hours=24, age_hours=48)
    _order(db, buyer, farmer, past)
    _order(db, buyer, farmer, past)
    make_listing(farmer, category=tomatoes)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert rows[0]['reason'] == 'You have ordered Tomato 2 times before'

# --------------------------------------------------------------------------
# Farmer affinity
# --------------------------------------------------------------------------

def test_a_repeat_farmer_outranks_a_new_one(client, db, auth, make_user, make_category, make_listing):
    known = make_user('known@test.demo', 'farmer', name='Anita Verma')
    stranger = make_user('new@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    # Both listings share a category, so only the farmer signal separates them.
    category = make_category(name='Tomato')
    past = make_listing(known, category=category, lifespan_hours=24, age_hours=48)
    _order(db, buyer, known, past)
    make_listing(stranger, category=category, lifespan_hours=96, age_hours=1)
    mine = make_listing(known, category=category, lifespan_hours=96, age_hours=50)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert rows[0]['id'] == mine.id

def test_reason_names_the_farmer_when_the_category_is_new(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer', name='Anita Verma')
    buyer = make_user('buyer@test.demo', 'buyer')
    ordered_category = make_category(name='Tomato')
    other_category = make_category(name='Spinach')
    past = make_listing(farmer, category=ordered_category, lifespan_hours=24, age_hours=48)
    _order(db, buyer, farmer, past)
    make_listing(farmer, category=other_category)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert rows[0]['reason'] == 'You have ordered from Anita Verma before'

def test_cancelled_orders_do_not_build_a_preference(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    tomatoes = make_category(name='Tomato')
    past = make_listing(farmer, category=tomatoes, lifespan_hours=24, age_hours=48)
    _order(db, buyer, farmer, past, status='cancelled')
    make_listing(farmer, category=tomatoes)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    # The buyer withdrew, so there is nothing to go on and the fallback applies.
    assert rows[0]['reason'] == 'Fresh today'

# --------------------------------------------------------------------------
# What never appears
# --------------------------------------------------------------------------

def test_expired_listings_are_never_recommended(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer, lifespan_hours=24, age_hours=48)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert rows == []

def test_suspended_listings_are_never_recommended(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    client.patch(f'/admin/listings/{listing.id}/status', json={'status': 'suspended'}, headers=auth(admin))

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert rows == []

def test_at_most_four_are_returned(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    for _ in range(6):
        make_listing(farmer)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert len(rows) == 4

def test_anonymous_cannot_read_recommendations(client):
    r = client.get('/recommendations/listings')

    assert r.status_code == 401

def test_a_farmer_with_no_buyer_history_gets_freshness_order(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    other = make_user('other@test.demo', 'farmer')
    older = make_listing(other, lifespan_hours=96, age_hours=60)
    newer = make_listing(other, lifespan_hours=96, age_hours=5)

    # Ordering is buyer-only, so a farmer's history is always empty. They must
    # still get a sensible list rather than an error or an empty page.
    rows = client.get('/recommendations/listings', headers=auth(farmer)).json()

    assert [r['id'] for r in rows] == [newer.id, older.id]
