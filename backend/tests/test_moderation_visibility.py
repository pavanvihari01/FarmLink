"""What the public listing endpoints expose, and to whom.

A suspended listing was reachable by direct URL, and an admin's moderation note
travelled on every listing response. Both are now gated on who is asking.

The rule these tests pin down: the owning farmer and admins see the full record
in any state, everyone else sees only active listings with no moderation text.
"""
from app.models.entities import Listing

def _suspend(client, auth, admin, listing_id, note=None):
    return client.patch(
        f'/admin/listings/{listing_id}/status',
        json={'status': 'suspended', 'moderation_note': note},
        headers=auth(admin),
    )

# --------------------------------------------------------------------------
# Who can reach a suspended listing
# --------------------------------------------------------------------------

def test_suspended_listing_is_hidden_from_anonymous(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id)

    r = client.get(f'/listings/{listing.id}')

    assert r.status_code == 404

def test_suspended_listing_is_hidden_from_another_buyer(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id)

    r = client.get(f'/listings/{listing.id}', headers=auth(buyer))

    assert r.status_code == 404

def test_suspended_listing_is_hidden_from_another_farmer(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    other = make_user('other@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id)

    r = client.get(f'/listings/{listing.id}', headers=auth(other))

    assert r.status_code == 404

def test_suspended_listing_is_visible_to_its_owner(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id)

    # The edit page loads through this endpoint. A 404 here would leave a
    # farmer unable to correct the listing an admin suspended.
    r = client.get(f'/listings/{listing.id}', headers=auth(farmer))

    assert r.status_code == 200
    assert r.json()['status'] == 'suspended'

def test_suspended_listing_is_visible_to_an_admin(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id)

    r = client.get(f'/listings/{listing.id}', headers=auth(admin))

    assert r.status_code == 200
    assert r.json()['status'] == 'suspended'

def test_active_listing_is_still_visible_to_anonymous(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)

    r = client.get(f'/listings/{listing.id}')

    assert r.status_code == 200

def test_removed_listing_stays_hidden_from_anonymous(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    client.patch(
        f'/admin/listings/{listing.id}/status',
        json={'status': 'removed'},
        headers=auth(admin),
    )

    r = client.get(f'/listings/{listing.id}')

    assert r.status_code == 404

# --------------------------------------------------------------------------
# Who can read a moderation note
# --------------------------------------------------------------------------

def test_moderation_note_is_not_public(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id, note='Repeated reports of incorrect quantity')

    # Reactivating puts the listing back on the marketplace. The note the admin
    # left must not travel with it.
    client.patch(f'/admin/listings/{listing.id}/status', json={'status': 'active'}, headers=auth(admin))

    body = client.get(f'/listings/{listing.id}').json()

    assert body['moderation_note'] is None

def test_moderation_note_is_hidden_from_another_buyer(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id, note='Pricing looks wrong')
    client.patch(f'/admin/listings/{listing.id}/status', json={'status': 'active'}, headers=auth(admin))

    body = client.get(f'/listings/{listing.id}', headers=auth(buyer)).json()

    assert body['moderation_note'] is None

def test_moderation_note_is_visible_to_the_owner(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id, note='Pricing looks wrong')

    body = client.get(f'/listings/{listing.id}', headers=auth(farmer)).json()

    assert body['moderation_note'] == 'Pricing looks wrong'

def test_farmer_listing_view_carries_the_moderation_note(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id, note='Pricing looks wrong')

    rows = client.get('/farmer/listings', headers=auth(farmer)).json()

    row = next(x for x in rows if x['id'] == listing.id)
    assert row['moderation_note'] == 'Pricing looks wrong'

def test_public_listing_list_never_carries_a_moderation_note(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id, note='Pricing looks wrong')
    client.patch(f'/admin/listings/{listing.id}/status', json={'status': 'active'}, headers=auth(admin))

    items = client.get('/listings').json()['items']

    assert len(items) == 1
    assert all(item['moderation_note'] is None for item in items)

def test_admin_listing_view_still_carries_the_moderation_note(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id, note='Pricing looks wrong')

    rows = client.get('/admin/listings', headers=auth(admin)).json()

    row = next(x for x in rows if x['id'] == listing.id)
    assert row['moderation_note'] == 'Pricing looks wrong'

def test_stale_token_does_not_break_the_public_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer)

    # A browser that still holds a dead token must not be locked out of the
    # public marketplace. optional_user degrades to anonymous; current_user
    # would have raised 401 and taken the whole catalogue down with it.
    r = client.get(
        f'/listings/{listing.id}',
        headers={'Authorization': 'Bearer not-a-real-token'},
    )

    assert r.status_code == 200

def test_stale_token_still_cannot_reach_a_suspended_listing(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    listing = make_listing(farmer)
    _suspend(client, auth, admin, listing.id)

    r = client.get(
        f'/listings/{listing.id}',
        headers={'Authorization': 'Bearer not-a-real-token'},
    )

    assert r.status_code == 404
