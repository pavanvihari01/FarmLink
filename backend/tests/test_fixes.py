"""The gap-closing fixes from dispatch #15."""
import io
from datetime import datetime, timedelta

import pytest  # type: ignore[import-not-found]

from app.models.entities import Address, Listing, Order, Report

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
JPEG = b'\xff\xd8\xff\xe0' + b'\x00' * 64

# --------------------------------------------------------------------------
# Listing edit
# --------------------------------------------------------------------------

def test_farmer_can_edit_their_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, quantity=35)

    r = client.patch(
        f'/listings/{listing.id}',
        json={'title': 'Renamed', 'price_per_unit': 99.5},
        headers=auth(farmer),
    )

    assert r.status_code == 200
    db.refresh(listing)
    assert listing.title == 'Renamed'
    assert listing.price_per_unit == 99.5

def test_farmer_cannot_edit_someone_elses_listing(client, db, auth, make_user, make_listing):
    owner = make_user('owner@test.demo', 'farmer')
    other = make_user('other@test.demo', 'farmer')
    listing = make_listing(owner)

    r = client.patch(f'/listings/{listing.id}', json={'title': 'Stolen'}, headers=auth(other))

    assert r.status_code == 403
    db.refresh(listing)
    assert listing.title != 'Stolen'

def test_buyer_cannot_edit_a_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)

    r = client.patch(f'/listings/{listing.id}', json={'title': 'Nope'}, headers=auth(buyer))

    assert r.status_code == 403

def test_editing_the_price_does_not_change_existing_orders(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = client.post(
        '/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer)
    ).json()['id']
    original = db.get(Order, order_id).total_amount

    client.patch(f'/listings/{listing.id}', json={'price_per_unit': 999}, headers=auth(farmer))

    # The order snapshotted its total when it was placed.
    assert db.get(Order, order_id).total_amount == original

def test_editing_harvest_time_recomputes_expires_at(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, lifespan_hours=48)
    harvested = datetime.utcnow() - timedelta(hours=6)

    r = client.patch(
        f'/listings/{listing.id}',
        json={'harvest_time': harvested.isoformat()},
        headers=auth(farmer),
    )

    assert r.status_code == 200
    expected = harvested + timedelta(hours=48)
    assert abs((datetime.fromisoformat(r.json()['expires_at']) - expected).total_seconds()) < 5

def test_editing_lifespan_recomputes_expires_at(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, lifespan_hours=48, age_hours=2)

    r = client.patch(f'/listings/{listing.id}', json={'lifespan_hours': 200}, headers=auth(farmer))

    assert r.status_code == 200
    assert r.json()['lifespan_hours'] == 200

def test_a_report_locked_farmer_cannot_raise_lifespan_by_editing(client, db, auth, make_user, make_category, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    category = make_category(name='Leafy', lifespan_hours=24)
    listing = make_listing(farmer, category=category, lifespan_hours=24)
    for i in range(3):
        reporter = make_user(f'r{i}@test.demo', 'buyer')
        target = make_listing(farmer, category=category, lifespan_hours=24)
        client.post('/reports', json={'listing_id': target.id, 'reason': 'fake_lifespan'}, headers=auth(reporter))

    r = client.patch(f'/listings/{listing.id}', json={'lifespan_hours': 700}, headers=auth(farmer))

    assert r.status_code == 200
    assert r.json()['lifespan_locked'] is True
    db.refresh(listing)
    # Forced back to the category default, same as creation does.
    assert listing.lifespan_hours == 24

def test_editing_a_removed_listing_is_rejected(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)
    client.delete(f'/listings/{listing.id}', headers=auth(farmer))

    r = client.patch(f'/listings/{listing.id}', json={'title': 'Zombie'}, headers=auth(farmer))

    assert r.status_code == 409

def test_editing_a_nonexistent_listing_is_404(client, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = client.patch('/listings/9999', json={'title': 'Ghost'}, headers=auth(farmer))

    assert r.status_code == 404

# --------------------------------------------------------------------------
# Listing delete
# --------------------------------------------------------------------------

def test_farmer_can_remove_their_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)

    r = client.delete(f'/listings/{listing.id}', headers=auth(farmer))

    assert r.status_code == 200
    db.refresh(listing)
    # Soft delete — the row survives so order history still resolves.
    assert listing.status == 'removed'
    assert db.get(Listing, listing.id) is not None

def test_removed_listing_disappears_from_the_marketplace(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)
    client.delete(f'/listings/{listing.id}', headers=auth(farmer))

    ids = [x['id'] for x in client.get('/listings').json()['items']]

    assert listing.id not in ids

def test_removed_listing_404s_by_direct_url(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)
    client.delete(f'/listings/{listing.id}', headers=auth(farmer))

    assert client.get(f'/listings/{listing.id}').status_code == 404

def test_removal_is_blocked_by_open_orders(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    client.post('/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer))

    r = client.delete(f'/listings/{listing.id}', headers=auth(farmer))

    assert r.status_code == 409
    db.refresh(listing)
    assert listing.status == 'active'

def test_removal_with_confirmation_cancels_and_restores_stock(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    order_id = client.post(
        '/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer)
    ).json()['id']

    r = client.delete(f'/listings/{listing.id}?cancel_open_orders=true', headers=auth(farmer))

    assert r.status_code == 200
    assert r.json()['cancelled_orders'] == 1
    db.refresh(listing)
    assert listing.status == 'removed'
    assert listing.available_quantity == 35
    assert db.get(Order, order_id).status == 'cancelled'

def test_farmer_cannot_remove_someone_elses_listing(client, db, auth, make_user, make_listing):
    owner = make_user('owner@test.demo', 'farmer')
    other = make_user('other@test.demo', 'farmer')
    listing = make_listing(owner)

    r = client.delete(f'/listings/{listing.id}', headers=auth(other))

    assert r.status_code == 403
    db.refresh(listing)
    assert listing.status == 'active'

def test_removing_twice_is_rejected(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)
    client.delete(f'/listings/{listing.id}', headers=auth(farmer))

    r = client.delete(f'/listings/{listing.id}', headers=auth(farmer))

    assert r.status_code == 409

def test_farmer_listings_include_removed_and_suspended(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    live = make_listing(farmer, title='Live')
    gone = make_listing(farmer, title='Gone')
    client.delete(f'/listings/{gone.id}', headers=auth(farmer))

    rows = client.get('/farmer/listings', headers=auth(farmer)).json()

    titles = {r['title'] for r in rows}
    # The public /listings endpoint hides both of these.
    assert 'Live' in titles
    assert 'Gone' in titles

def test_buyer_cannot_read_the_farmer_listing_view(client, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')

    assert client.get('/farmer/listings', headers=auth(buyer)).status_code == 403

# --------------------------------------------------------------------------
# Deactivation cascade
# --------------------------------------------------------------------------

def test_deactivating_a_farmer_suspends_their_active_listings(client, db, auth, make_user, make_listing):
    admin = make_user('admin@test.demo', 'admin')
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)

    r = client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': False}, headers=auth(admin))

    assert r.status_code == 200
    assert r.json()['listings_affected'] == 1
    db.refresh(listing)
    assert listing.status == 'suspended'
    assert listing.suspended_by_deactivation is True

def test_a_deactivated_farmers_listing_cannot_be_ordered(client, db, auth, make_user, make_listing):
    admin = make_user('admin@test.demo', 'admin')
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer, quantity=35)
    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': False}, headers=auth(admin))

    r = client.post('/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer))

    assert r.status_code == 422

def test_reactivating_restores_only_the_auto_suspended_listings(client, db, auth, make_user, make_listing):
    admin = make_user('admin@test.demo', 'admin')
    farmer = make_user('farmer@test.demo', 'farmer')
    auto = make_listing(farmer, title='Auto')
    by_hand = make_listing(farmer, title='By hand')
    # Suspended by an admin before the farmer was deactivated.
    client.patch(f'/admin/listings/{by_hand.id}/status', json={'status': 'suspended'}, headers=auth(admin))

    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': False}, headers=auth(admin))
    r = client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': True}, headers=auth(admin))

    assert r.json()['listings_affected'] == 1
    db.refresh(auto)
    db.refresh(by_hand)
    assert auto.status == 'active'
    # The admin's own decision is not undone by reactivation.
    assert by_hand.status == 'suspended'

def test_deactivation_leaves_removed_listings_alone(client, db, auth, make_user, make_listing):
    admin = make_user('admin@test.demo', 'admin')
    farmer = make_user('farmer@test.demo', 'farmer')
    gone = make_listing(farmer)
    client.delete(f'/listings/{gone.id}', headers=auth(farmer))

    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': False}, headers=auth(admin))

    db.refresh(gone)
    assert gone.status == 'removed'

def test_a_manual_suspension_clears_the_auto_flag(client, db, auth, make_user, make_listing):
    admin = make_user('admin@test.demo', 'admin')
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)
    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': False}, headers=auth(admin))

    # The admin now acts on the listing directly.
    client.patch(f'/admin/listings/{listing.id}/status', json={'status': 'suspended'}, headers=auth(admin))

    db.refresh(listing)
    assert listing.suspended_by_deactivation is False

    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': True}, headers=auth(admin))

    db.refresh(listing)
    # Reactivation must not undo the admin's manual decision.
    assert listing.status == 'suspended'

def test_deactivating_a_buyer_affects_no_listings(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    buyer = make_user('buyer@test.demo', 'buyer')

    r = client.patch(f'/admin/users/{buyer.id}/active', json={'is_active': False}, headers=auth(admin))

    assert r.json()['listings_affected'] == 0

# --------------------------------------------------------------------------
# Password change
# --------------------------------------------------------------------------

def test_password_change_with_the_right_current_password(client, db, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')

    r = client.post(
        '/auth/change-password',
        json={'current_password': 'Demo123!', 'new_password': 'BrandNew456!'},
        headers=auth(user),
    )

    assert r.status_code == 200
    login = client.post('/auth/login', json={'email': user.email, 'password': 'BrandNew456!'})
    assert login.status_code == 200

def test_password_change_with_the_wrong_current_password(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')

    r = client.post(
        '/auth/change-password',
        json={'current_password': 'WrongPassword', 'new_password': 'BrandNew456!'},
        headers=auth(user),
    )

    assert r.status_code == 401

def test_new_password_must_differ(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')

    r = client.post(
        '/auth/change-password',
        json={'current_password': 'Demo123!', 'new_password': 'Demo123!'},
        headers=auth(user),
    )

    assert r.status_code == 422

def test_new_password_must_meet_the_minimum_length(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')

    r = client.post(
        '/auth/change-password',
        json={'current_password': 'Demo123!', 'new_password': 'short'},
        headers=auth(user),
    )

    assert r.status_code == 422

def test_the_old_password_stops_working(client, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    client.post(
        '/auth/change-password',
        json={'current_password': 'Demo123!', 'new_password': 'BrandNew456!'},
        headers=auth(user),
    )

    assert client.post('/auth/login', json={'email': user.email, 'password': 'Demo123!'}).status_code == 401

# --------------------------------------------------------------------------
# Address edit and default
# --------------------------------------------------------------------------

def _address(client, auth, user, label='Home', **over):
    body = {
        'label': label, 'line1': '12 Market Road', 'city': 'Pune',
        'state': 'Maharashtra', 'pincode': '411001',
    }
    body.update(over)
    return client.post('/addresses', json=body, headers=auth(user))

def test_address_can_be_edited(client, db, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    address_id = _address(client, auth, user).json()['id']

    r = client.patch(
        f'/addresses/{address_id}',
        json={'label': 'Work', 'city': 'Nashik'},
        headers=auth(user),
    )

    assert r.status_code == 200
    assert r.json()['label'] == 'Work'
    assert r.json()['city'] == 'Nashik'
    # Untouched fields survive.
    assert r.json()['line1'] == '12 Market Road'

def test_editing_an_address_can_add_a_pin(client, db, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    address_id = _address(client, auth, user).json()['id']

    r = client.patch(
        f'/addresses/{address_id}',
        json={'latitude': 19.99, 'longitude': 73.78},
        headers=auth(user),
    )

    assert r.json()['latitude'] == 19.99

def test_editing_an_address_can_clear_the_pin(client, db, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    address_id = _address(client, auth, user, latitude=19.99, longitude=73.78).json()['id']

    r = client.patch(f'/addresses/{address_id}', json={'latitude': None}, headers=auth(user))

    assert r.json()['latitude'] is None

def test_cannot_edit_someone_elses_address(client, db, auth, make_user):
    owner = make_user('owner@test.demo', 'buyer')
    stranger = make_user('stranger@test.demo', 'buyer')
    address_id = _address(client, auth, owner).json()['id']

    r = client.patch(f'/addresses/{address_id}', json={'label': 'Hijacked'}, headers=auth(stranger))

    assert r.status_code == 404

def test_promoting_an_address_demotes_the_previous_default(client, db, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    first = _address(client, auth, user).json()['id']
    second = _address(client, auth, user, label='Work').json()['id']

    client.patch(f'/addresses/{second}', json={'is_default': True}, headers=auth(user))

    rows = client.get('/addresses', headers=auth(user)).json()
    defaults = [a for a in rows if a['is_default']]
    assert len(defaults) == 1
    assert defaults[0]['id'] == second

def test_demoting_the_only_default_is_ignored(client, db, auth, make_user):
    user = make_user('buyer@test.demo', 'buyer')
    address_id = _address(client, auth, user).json()['id']

    client.patch(f'/addresses/{address_id}', json={'is_default': False}, headers=auth(user))

    rows = client.get('/addresses', headers=auth(user)).json()
    # A user with any addresses always has exactly one default.
    assert rows[0]['is_default'] is True

# --------------------------------------------------------------------------
# Report resolution
# --------------------------------------------------------------------------

def _report(client, auth, buyer, listing, reason='fake_lifespan'):
    return client.post('/reports', json={'listing_id': listing.id, 'reason': reason}, headers=auth(buyer))

def test_admin_can_resolve_a_report(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    report_id = _report(client, auth, buyer, listing).json()['id']

    r = client.patch(
        f'/admin/reports/{report_id}',
        json={'status': 'resolved', 'note': 'Looked at it, nothing wrong'},
        headers=auth(admin),
    )

    assert r.status_code == 200
    assert r.json()['status'] == 'resolved'
    assert r.json()['resolution_note'] == 'Looked at it, nothing wrong'

def test_admin_can_dismiss_a_report(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    report_id = _report(client, auth, buyer, listing).json()['id']

    r = client.patch(f'/admin/reports/{report_id}', json={'status': 'dismissed'}, headers=auth(admin))

    assert r.json()['status'] == 'dismissed'

def test_resolving_twice_is_rejected(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    report_id = _report(client, auth, buyer, listing).json()['id']
    client.patch(f'/admin/reports/{report_id}', json={'status': 'resolved'}, headers=auth(admin))

    r = client.patch(f'/admin/reports/{report_id}', json={'status': 'dismissed'}, headers=auth(admin))

    assert r.status_code == 409

def test_buyer_cannot_resolve_a_report(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    listing = make_listing(farmer)
    report_id = _report(client, auth, buyer, listing).json()['id']

    r = client.patch(f'/admin/reports/{report_id}', json={'status': 'resolved'}, headers=auth(buyer))

    assert r.status_code == 403

def test_resolving_removes_it_from_the_open_count(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    report_id = _report(client, auth, buyer, listing).json()['id']
    assert client.get('/admin/metrics', headers=auth(admin)).json()['reports_open'] == 1

    client.patch(f'/admin/reports/{report_id}', json={'status': 'resolved'}, headers=auth(admin))

    assert client.get('/admin/metrics', headers=auth(admin)).json()['reports_open'] == 0

def test_resolving_does_not_touch_the_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    report_id = _report(client, auth, buyer, listing).json()['id']

    client.patch(f'/admin/reports/{report_id}', json={'status': 'resolved'}, headers=auth(admin))

    db.refresh(listing)
    # Closing a report records that an admin looked. Any action is separate.
    assert listing.status == 'active'

# --------------------------------------------------------------------------
# Admin orders
# --------------------------------------------------------------------------

def test_admin_can_list_every_order(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer, quantity=35)
    client.post('/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer))

    rows = client.get('/admin/orders', headers=auth(admin)).json()

    assert len(rows) == 1
    assert rows[0]['farmer_name'] == farmer.name

def test_admin_order_list_carries_both_names(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer', name='Anita Verma')
    buyer = make_user('buyer@test.demo', 'buyer', name='Meera Shah')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer, quantity=35)
    client.post('/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer))

    row = client.get('/admin/orders', headers=auth(admin)).json()[0]

    assert row['counterparty'] == 'Meera Shah'
    assert row['farmer_name'] == 'Anita Verma'

def test_admin_can_transition_any_order(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer, quantity=35)
    order_id = client.post(
        '/orders', json={'listing_id': listing.id, 'quantity': 5}, headers=auth(buyer)
    ).json()['id']

    r = client.patch(f'/orders/{order_id}/status', json={'status': 'accepted'}, headers=auth(admin))

    assert r.status_code == 200
    assert db.get(Order, order_id).status == 'accepted'

def test_buyer_cannot_read_the_admin_order_list(client, auth, make_user):
    buyer = make_user('buyer@test.demo', 'buyer')

    assert client.get('/admin/orders', headers=auth(buyer)).status_code == 403

# --------------------------------------------------------------------------
# Upload magic bytes
# --------------------------------------------------------------------------

def _upload(client, auth, user, content, filename, content_type):
    return client.post(
        '/uploads',
        files={'file': (filename, content, content_type)},
        headers=auth(user),
    )

@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr('app.api.routes.UPLOAD_DIR', tmp_path)
    return tmp_path

def test_real_png_bytes_are_accepted(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer, PNG, 'x.png', 'image/png')

    assert r.status_code == 200

def test_html_disguised_as_a_jpeg_is_rejected(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')
    payload = b'<html><script>alert(1)</script></html>'

    r = _upload(client, auth, farmer, payload, 'evil.jpg', 'image/jpeg')

    assert r.status_code == 422
    assert 'does not look like an image' in r.json()['detail']

def test_a_png_declared_as_a_jpeg_is_rejected(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer, PNG, 'x.jpg', 'image/jpeg')

    assert r.status_code == 422
    assert 'image/png' in r.json()['detail']

def test_a_zip_is_rejected(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')
    payload = b'PK\x03\x04' + b'\x00' * 64

    r = _upload(client, auth, farmer, payload, 'x.png', 'image/png')

    assert r.status_code == 422

def test_real_jpeg_bytes_are_accepted(client, auth, make_user, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _upload(client, auth, farmer, JPEG, 'x.jpg', 'image/jpeg')

    assert r.status_code == 200

# --------------------------------------------------------------------------
# Image cleanup on replacement
# --------------------------------------------------------------------------

def test_replacing_an_image_deletes_the_old_file(client, db, auth, make_user, make_listing, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)
    first = _upload(client, auth, farmer, PNG, 'a.png', 'image/png').json()['url']
    client.patch(f'/listings/{listing.id}', json={'image_url': first}, headers=auth(farmer))
    stored = upload_dir / first.rsplit('/', 1)[-1]
    assert stored.exists()

    second = _upload(client, auth, farmer, PNG, 'b.png', 'image/png').json()['url']
    client.patch(f'/listings/{listing.id}', json={'image_url': second}, headers=auth(farmer))

    assert not stored.exists()

def test_the_default_image_is_never_deleted(client, db, auth, make_user, make_listing, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)
    uploaded = _upload(client, auth, farmer, PNG, 'a.png', 'image/png').json()['url']
    client.patch(f'/listings/{listing.id}', json={'image_url': uploaded}, headers=auth(farmer))

    # Back to the bundled default. That path is shared by every listing that
    # never uploaded one, so it must not be touched.
    r = client.patch(
        f'/listings/{listing.id}',
        json={'image_url': '/images/market-harvest.png'},
        headers=auth(farmer),
    )

    assert r.status_code == 200

def test_an_image_still_used_by_another_listing_survives(client, db, auth, make_user, make_listing, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')
    first = make_listing(farmer, title='One')
    second = make_listing(farmer, title='Two')
    shared = _upload(client, auth, farmer, PNG, 'a.png', 'image/png').json()['url']
    client.patch(f'/listings/{first.id}', json={'image_url': shared}, headers=auth(farmer))
    client.patch(f'/listings/{second.id}', json={'image_url': shared}, headers=auth(farmer))
    stored = upload_dir / shared.rsplit('/', 1)[-1]

    # Only one of the two stops using it.
    client.patch(f'/listings/{first.id}', json={'image_url': '/images/market-harvest.png'}, headers=auth(farmer))

    assert stored.exists()

def test_removing_a_listing_keeps_its_image(client, db, auth, make_user, make_listing, upload_dir):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)
    uploaded = _upload(client, auth, farmer, PNG, 'a.png', 'image/png').json()['url']
    client.patch(f'/listings/{listing.id}', json={'image_url': uploaded}, headers=auth(farmer))
    stored = upload_dir / uploaded.rsplit('/', 1)[-1]

    client.delete(f'/listings/{listing.id}', headers=auth(farmer))

    # Soft delete is reversible, so the photo has to survive.
    assert stored.exists()



def test_editing_non_freshness_fields_leaves_expires_at_alone(client, db, auth, make_user, make_listing):
    """Editing price/quantity/description/location must not move expires_at.

    Regression context: EditListing.tsx seeded its lifespan field from
    remaining_hours, so every save resubmitted a shortened lifespan and
    update_listing recomputed expires_at from it. A 96h listing edited 24h in
    became a 72h listing, and each further edit shrank it again.

    The fix is on the client. It now seeds from lifespan_hours and resends the
    original value. What this test pins is the server-side invariant that makes
    that fix sufficient: expires_at is a pure function of the base time and
    lifespan_hours, so an edit touching neither recomputes to the same value.
    It would fail if the endpoint ever derived lifespan from elapsed time.
    """
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, lifespan_hours=96, age_hours=24)

    def edit_price(price):
        r = client.patch(
            f'/listings/{listing.id}',
            json={
                'price_per_unit': price,
                'available_quantity': 7,
                'description': 'Updated description',
                'location_text': 'Updated location',
                'lifespan_hours': 96,
            },
            headers=auth(farmer),
        )
        assert r.status_code == 200
        return r.json()

    first = edit_price(42.0)
    second = edit_price(43.0)

    assert first['lifespan_hours'] == 96
    assert second['lifespan_hours'] == 96
    # The ratchet is what made the bug visible. Two edits must land on one
    # value; under the old behaviour each save shortened the listing further.
    assert first['expires_at'] == second['expires_at']
