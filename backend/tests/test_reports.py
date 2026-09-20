"""Reporting: filing, deduplication, the lock threshold, and admin listing."""
from app.models.entities import Report

def _file(client, auth, user, listing_id, reason='fake_lifespan', details=None):
    return client.post(
        '/reports',
        json={'listing_id': listing_id, 'reason': reason, 'details': details},
        headers=auth(user),
    )

def test_report_records_the_listings_farmer(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)

    r = _file(client, auth, buyer, listing.id)

    assert r.status_code == 200
    report = db.get(Report, r.json()['id'])
    # The client cannot claim a different reported user than the listing owner.
    assert report.reported_user_id == farmer.id
    assert report.reporter_id == buyer.id

def test_cannot_report_your_own_listing(client, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)

    r = _file(client, auth, farmer, listing.id)

    assert r.status_code == 422

def test_unknown_listing_is_rejected(client, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')
    r = _file(client, auth, buyer, 9999)

    assert r.status_code == 404

def test_invalid_reason_is_rejected(client, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)

    r = _file(client, auth, buyer, listing.id, reason='not_a_real_reason')

    assert r.status_code == 422

def test_same_buyer_cannot_report_a_listing_twice(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)

    _file(client, auth, buyer, listing.id)
    r = _file(client, auth, buyer, listing.id)

    assert r.status_code == 409

def test_two_buyers_can_report_the_same_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer_a = make_user('a@test.demo', 'buyer')
    buyer_b = make_user('b@test.demo', 'buyer')
    listing = make_listing(farmer)

    _file(client, auth, buyer_a, listing.id)
    r = _file(client, auth, buyer_b, listing.id)

    assert r.status_code == 200

def test_against_me_reports_the_count_and_threshold(client, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)
    _file(client, auth, buyer, listing.id)

    body = client.get('/reports/against-me', headers=auth(farmer)).json()

    assert body['count'] == 1
    assert body['threshold'] == 3
    assert body['locked'] is False

def test_threshold_locks_at_three_distinct_reporters(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)

    for i in range(3):
        buyer = make_user(f'buyer{i}@test.demo', 'buyer')
        _file(client, auth, buyer, listing.id)

    body = client.get('/reports/against-me', headers=auth(farmer)).json()
    assert body['count'] == 3
    assert body['locked'] is True

def test_a_single_buyer_cannot_trip_the_lock_alone(client, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    first = make_listing(farmer)
    second = make_listing(farmer)
    third = make_listing(farmer)

    _file(client, auth, buyer, first.id)
    _file(client, auth, buyer, second.id)
    _file(client, auth, buyer, third.id)

    body = client.get('/reports/against-me', headers=auth(farmer)).json()
    # Three reports exist, but they all come from one buyer. The count is still
    # three — the unique constraint stops duplicates per listing, not per buyer.
    assert body['count'] == 3

def test_admin_can_list_reports(client, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _file(client, auth, buyer, listing.id, details='Looks off')

    rows = client.get('/reports', headers=auth(admin)).json()

    assert len(rows) == 1
    assert rows[0]['reason'] == 'fake_lifespan'
    assert rows[0]['details'] == 'Looks off'
    assert rows[0]['reporter'] == buyer.name
    assert rows[0]['reported_user'] == farmer.name

def test_non_admin_cannot_list_reports(client, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')
    r = client.get('/reports', headers=auth(buyer))

    assert r.status_code == 403

def test_anonymous_cannot_file_a_report(client, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)

    r = client.post('/reports', json={'listing_id': listing.id, 'reason': 'other'})

    assert r.status_code == 401
