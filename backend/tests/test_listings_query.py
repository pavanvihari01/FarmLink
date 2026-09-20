"""Search, filtering, sorting, and pagination on GET /listings.

Also covers expires_at: that it is written on create, and that the freshness
helper prefers it over recomputing from harvest_time.
"""
from datetime import datetime, timedelta

from app.models.entities import Listing
from app.services.freshness import freshness

def _ids(response):
    return [x['id'] for x in response.json()['items']]

# --------------------------------------------------------------------------
# Response shape
# --------------------------------------------------------------------------

def test_response_is_a_paginated_envelope(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer)

    body = client.get('/listings').json()

    assert set(body) == {'items', 'total', 'page', 'pages', 'page_size'}
    assert body['total'] == 1
    assert body['page'] == 1
    assert body['pages'] == 1

def test_item_carries_the_new_detail_fields(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, description='Cut this morning', latitude=19.99, longitude=73.78)

    item = client.get('/listings').json()['items'][0]

    assert item['description'] == 'Cut this morning'
    assert item['latitude'] == 19.99
    assert item['longitude'] == 73.78
    assert item['bulk_available'] is False
    assert item['distance_km'] is None

# --------------------------------------------------------------------------
# expires_at
# --------------------------------------------------------------------------

def test_create_listing_stores_expires_at(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    category = make_category(lifespan_hours=48)

    r = client.post(
        '/listings',
        json={
            'category_id': category.id,
            'title': 'Spinach',
            'price_per_unit': 38,
            'available_quantity': 20,
            'lifespan_hours': 48,
            'location_text': 'Pune',
        },
        headers=auth(farmer),
    )

    assert r.status_code == 200
    created = db.get(Listing, r.json()['id'])
    assert created.expires_at is not None
    # No harvest time given, so the base is the moment of listing.
    delta = created.expires_at - created.listing_time
    assert abs(delta.total_seconds() - 48 * 3600) < 5

def test_expires_at_uses_harvest_time_when_given(client, db, auth, make_user, make_category):
    farmer = make_user('farmer@test.demo', 'farmer')
    category = make_category(lifespan_hours=24)
    harvested = datetime.utcnow() - timedelta(hours=6)

    r = client.post(
        '/listings',
        json={
            'category_id': category.id,
            'title': 'Spinach',
            'price_per_unit': 38,
            'available_quantity': 20,
            'lifespan_hours': 24,
            'harvest_time': harvested.isoformat(),
            'location_text': 'Pune',
        },
        headers=auth(farmer),
    )

    created = db.get(Listing, r.json()['id'])
    assert abs((created.expires_at - (harvested + timedelta(hours=24))).total_seconds()) < 5

def test_freshness_prefers_the_stored_column():
    # expires_at says 2 hours left. harvest_time plus lifespan would say
    # something different. The column wins.
    listing = type('L', (), {
        # A minute of slack. freshness floors the remaining hours, so an
        # expires_at of exactly now+2h reads back as 1 once any time at all has
        # passed between building this object and calling the helper.
        'expires_at': datetime.utcnow() + timedelta(hours=2, minutes=1),
        'harvest_time': datetime.utcnow() - timedelta(hours=90),
        'listing_time': datetime.utcnow() - timedelta(hours=90),
        'lifespan_hours': 96,
    })()

    status, hours = freshness(listing)

    assert hours == 2

def test_freshness_falls_back_when_the_column_is_absent():
    # The existing freshness fixtures are SimpleNamespace objects with no
    # expires_at. The helper must keep working on them.
    listing = type('L', (), {
        'harvest_time': datetime.utcnow() - timedelta(hours=10),
        'listing_time': datetime.utcnow(),
        'lifespan_hours': 96,
    })()

    assert freshness(listing)[0] == 'Fresh'

# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------

def test_expired_listings_are_never_returned(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, lifespan_hours=24, age_hours=48)

    body = client.get('/listings').json()

    assert body['total'] == 0

def test_filter_by_category(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    tomatoes = make_category(name='Tomato', lifespan_hours=96)
    spinach = make_category(name='Spinach', lifespan_hours=24)
    keep = make_listing(farmer, category=tomatoes)
    make_listing(farmer, category=spinach)

    body = client.get(f'/listings?category_id={tomatoes.id}').json()

    assert body['total'] == 1
    assert _ids(client.get(f'/listings?category_id={tomatoes.id}')) == [keep.id]

def test_filter_by_price_range(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    cheap = make_listing(farmer, price_per_unit=10)
    mid = make_listing(farmer, price_per_unit=40)
    pricey = make_listing(farmer, price_per_unit=90)

    body = client.get('/listings?min_price=20&max_price=50').json()

    assert body['total'] == 1
    assert _ids(client.get('/listings?min_price=20&max_price=50')) == [mid.id]

def test_filter_organic(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, organic=False)
    organic = make_listing(farmer, organic=True)

    body = client.get('/listings?organic=true').json()

    assert body['total'] == 1
    assert _ids(client.get('/listings?organic=true')) == [organic.id]

def test_filter_bulk_available(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, bulk_available=False)
    bulk = make_listing(farmer, bulk_available=True)

    body = client.get('/listings?bulk_available=true').json()

    assert body['total'] == 1
    assert _ids(client.get('/listings?bulk_available=true')) == [bulk.id]

def test_filter_by_location_text(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, location_text='Nashik, Maharashtra')
    make_listing(farmer, location_text='Pune, Maharashtra')

    body = client.get('/listings?location=nashik').json()

    assert body['total'] == 1

def test_filter_by_farmer_name(client, db, auth, make_user, make_listing):
    anita = make_user('anita@test.demo', 'farmer', name='Anita Verma')
    raj = make_user('raj@test.demo', 'farmer', name='Raj Singh')
    make_listing(anita)
    make_listing(raj)

    body = client.get('/listings?farmer=anita').json()

    assert body['total'] == 1

def test_filter_by_freshness_status(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, lifespan_hours=96, age_hours=10)   # Fresh
    make_listing(farmer, lifespan_hours=96, age_hours=50)   # Use Soon

    fresh = client.get('/listings?freshness_status=Fresh').json()
    use_soon = client.get('/listings?freshness_status=Use Soon').json()

    assert fresh['total'] == 1
    assert use_soon['total'] == 1
    assert fresh['items'][0]['freshness_status'] == 'Fresh'

def test_unknown_freshness_status_is_rejected(client):
    r = client.get('/listings?freshness_status=Rotten')

    assert r.status_code == 422

def test_text_search_matches_title_and_location(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, title='Vine-ripe Tomatoes', location_text='Nashik')
    make_listing(farmer, title='Morning Spinach', location_text='Pune')

    assert client.get('/listings?q=tomato').json()['total'] == 1
    assert client.get('/listings?q=pune').json()['total'] == 1
    assert client.get('/listings?q=zzz').json()['total'] == 0

def test_filters_combine(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    tomatoes = make_category(name='Tomato', lifespan_hours=96)
    make_listing(farmer, category=tomatoes, price_per_unit=10, organic=True)
    make_listing(farmer, category=tomatoes, price_per_unit=90, organic=True)
    make_listing(farmer, category=tomatoes, price_per_unit=10, organic=False)

    body = client.get(f'/listings?category_id={tomatoes.id}&max_price=50&organic=true').json()

    assert body['total'] == 1

# --------------------------------------------------------------------------
# Sorting
# --------------------------------------------------------------------------

def test_sort_price_ascending(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, price_per_unit=50)
    make_listing(farmer, price_per_unit=10)
    make_listing(farmer, price_per_unit=30)

    items = client.get('/listings?sort=price_asc').json()['items']

    assert [i['price_per_unit'] for i in items] == [10, 30, 50]

def test_sort_price_descending(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, price_per_unit=50)
    make_listing(farmer, price_per_unit=10)

    items = client.get('/listings?sort=price_desc').json()['items']

    assert [i['price_per_unit'] for i in items] == [50, 10]

def test_sort_newest(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    old = make_listing(farmer, age_hours=5)
    new = make_listing(farmer, age_hours=1)

    ids = _ids(client.get('/listings?sort=newest'))

    assert ids == [new.id, old.id]

def test_sort_freshness_is_the_default(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    # Same lifespan, different ages: the younger one has more hours left.
    older = make_listing(farmer, lifespan_hours=96, age_hours=60)
    newer = make_listing(farmer, lifespan_hours=96, age_hours=5)

    default_ids = _ids(client.get('/listings'))
    explicit_ids = _ids(client.get('/listings?sort=freshness'))

    assert default_ids == [newer.id, older.id]
    assert explicit_ids == default_ids

def test_unknown_sort_is_rejected(client):
    r = client.get('/listings?sort=alphabetical')

    assert r.status_code == 422

# --------------------------------------------------------------------------
# Distance
# --------------------------------------------------------------------------

def test_distance_is_computed_when_coordinates_are_supplied(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    # Nashik, and a point roughly 1 degree of latitude south.
    make_listing(farmer, latitude=19.9975, longitude=73.7898)

    item = client.get('/listings?lat=18.9975&lng=73.7898').json()['items'][0]

    # 1 degree of latitude is about 111 km.
    assert 105 < item['distance_km'] < 115

def test_distance_is_null_for_listings_without_a_pin(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer)

    item = client.get('/listings?lat=19.0&lng=73.0').json()['items'][0]

    assert item['distance_km'] is None

def test_sort_nearest_puts_unpinned_listings_last(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer, latitude=None, longitude=None)
    near = make_listing(farmer, latitude=19.05, longitude=73.79)
    far = make_listing(farmer, latitude=21.15, longitude=79.09)

    ids = _ids(client.get('/listings?sort=nearest&lat=19.0&lng=73.79'))

    assert ids[0] == near.id
    assert ids[1] == far.id
    # The unpinned listing is last, not first.
    assert ids[2] not in (near.id, far.id)

def test_sort_nearest_without_an_origin_is_rejected(client):
    r = client.get('/listings?sort=nearest')

    assert r.status_code == 422

# --------------------------------------------------------------------------
# Pagination
# --------------------------------------------------------------------------

def test_page_size_limits_the_page(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    for _ in range(5):
        make_listing(farmer)

    body = client.get('/listings?page_size=2').json()

    assert len(body['items']) == 2
    assert body['total'] == 5
    assert body['pages'] == 3

def test_pages_do_not_overlap(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    for i in range(5):
        make_listing(farmer, title=f'Produce {i}')

    first = _ids(client.get('/listings?page=1&page_size=2&sort=price_asc'))
    second = _ids(client.get('/listings?page=2&page_size=2&sort=price_asc'))

    assert len(first) == 2
    assert set(first).isdisjoint(second)

def test_page_beyond_the_end_clamps_to_the_last_page(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer)

    body = client.get('/listings?page=99').json()

    assert body['page'] == 1
    assert len(body['items']) == 1

def test_page_size_above_the_cap_is_rejected(client):
    r = client.get('/listings?page_size=500')

    assert r.status_code == 422

def test_page_zero_is_rejected(client):
    r = client.get('/listings?page=0')

    assert r.status_code == 422

def test_filters_apply_before_pagination(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    for _ in range(4):
        make_listing(farmer, price_per_unit=10)
    for _ in range(6):
        make_listing(farmer, price_per_unit=100)

    body = client.get('/listings?max_price=50&page_size=3').json()

    # 4 cheap listings survive the filter, so 2 pages — not 4 pages of 10.
    assert body['total'] == 4
    assert body['pages'] == 2

# --------------------------------------------------------------------------
# Recommendations still work
# --------------------------------------------------------------------------

def test_recommendations_returns_at_most_four(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    for _ in range(6):
        make_listing(farmer)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert len(rows) == 4

def test_recommendations_excludes_expired(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    make_listing(farmer, lifespan_hours=24, age_hours=48)

    rows = client.get('/recommendations/listings', headers=auth(buyer)).json()

    assert rows == []
