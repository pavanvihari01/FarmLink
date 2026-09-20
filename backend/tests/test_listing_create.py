"""Creating a listing, and the lifespan lock that applies to reported farmers."""
from app.models.entities import Category, Listing

def _category(db, lifespan=48, name='Leafy Greens'):
    c = Category(name=name, default_lifespan_hours=lifespan)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def _payload(category_id, **over):
    body = {
        'category_id': category_id,
        'title': 'Fresh Spinach',
        'description': 'Cut this morning.',
        'price_per_unit': 38,
        'unit': 'kg',
        'available_quantity': 20,
        'lifespan_hours': 24,
        'location_text': 'Pune, Maharashtra',
    }
    body.update(over)
    return body

def test_farmer_can_create_a_listing(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')
    category = _category(db)

    r = client.post('/listings', json=_payload(category.id), headers=auth(farmer))

    assert r.status_code == 200
    created = db.get(Listing, r.json()['id'])
    assert created.farmer_id == farmer.id
    assert created.title == 'Fresh Spinach'

def test_farmer_keeps_their_chosen_lifespan_when_not_reported(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')
    category = _category(db, lifespan=48)

    r = client.post('/listings', json=_payload(category.id, lifespan_hours=120), headers=auth(farmer))

    assert r.status_code == 200
    assert r.json()['lifespan_hours'] == 120

def test_lifespan_is_forced_to_the_category_default_when_locked(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    category = _category(db, lifespan=48)

    # Three distinct buyers each report one of the farmer's listings.
    for i in range(3):
        buyer = make_user(f'reporter{i}@test.demo', 'buyer')
        listing = make_listing(farmer)
        client.post(
            '/reports',
            json={'listing_id': listing.id, 'reason': 'fake_lifespan'},
            headers=auth(buyer),
        )

    # The farmer tries to claim a 30-day shelf life.
    r = client.post('/listings', json=_payload(category.id, lifespan_hours=720), headers=auth(farmer))

    assert r.status_code == 200
    # Replaced with the category default rather than rejected, so the form
    # still works and the stored value is the honest one.
    assert r.json()['lifespan_hours'] == 48
    created = db.get(Listing, r.json()['id'])
    assert created.lifespan_hours == 48

def test_lock_cannot_be_bypassed_by_posting_directly(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    category = _category(db, lifespan=24)

    for i in range(3):
        buyer = make_user(f'r{i}@test.demo', 'buyer')
        listing = make_listing(farmer)
        client.post('/reports', json={'listing_id': listing.id, 'reason': 'bad_quality'}, headers=auth(buyer))

    # Same request the UI would send with the field disabled — the client
    # supplies a value anyway. The server must ignore it.
    r = client.post('/listings', json=_payload(category.id, lifespan_hours=600), headers=auth(farmer))

    assert db.get(Listing, r.json()['id']).lifespan_hours == 24

def test_future_harvest_time_is_rejected(client, db, auth, make_user):
    from datetime import datetime, timedelta

    farmer = make_user('farmer@test.demo', 'farmer')
    category = _category(db)
    future = (datetime.utcnow() + timedelta(days=1)).isoformat()

    r = client.post('/listings', json=_payload(category.id, harvest_time=future), headers=auth(farmer))

    assert r.status_code == 422

def test_unknown_category_is_rejected(client, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = client.post('/listings', json=_payload(9999), headers=auth(farmer))

    assert r.status_code == 404

def test_buyer_cannot_create_a_listing(client, db, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')
    category = _category(db)

    r = client.post('/listings', json=_payload(category.id), headers=auth(buyer))

    assert r.status_code == 403

def test_coordinates_are_stored_when_supplied(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')
    category = _category(db)

    r = client.post(
        '/listings',
        json=_payload(category.id, latitude=19.9975, longitude=73.7898),
        headers=auth(farmer),
    )

    created = db.get(Listing, r.json()['id'])
    assert created.latitude == 19.9975
    assert created.longitude == 73.7898
