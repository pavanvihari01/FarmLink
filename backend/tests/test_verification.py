"""Farmer verification: the badge must reflect an admin decision.

Before this existed, listing_out computed `verified` as
`farmer.role == 'farmer'`. Only farmers can create listings, so that was true
for every listing in the marketplace — a badge that was always on and
therefore said nothing.

These tests pin the property that matters: a listing is unverified until an
admin says otherwise, and verifying one farmer does not verify another.
"""
from app.models.entities import User

def _verify(client, auth, actor, user_id, status='verified'):
    return client.patch(
        f'/admin/users/{user_id}/verification',
        json={'verification_status': status},
        headers=auth(actor),
    )

def test_listing_is_unverified_until_an_admin_says_otherwise(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    make_listing(farmer)

    body = client.get('/listings').json()

    assert body['items'][0]['verified'] is False

def test_admin_can_verify_a_farmer(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    make_listing(farmer)

    r = _verify(client, auth, admin, farmer.id)

    assert r.status_code == 200
    db.refresh(farmer)
    assert farmer.verification_status == 'verified'
    assert client.get('/listings').json()['items'][0]['verified'] is True

def test_verification_can_be_taken_away(client, db, auth, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    make_listing(farmer)
    _verify(client, auth, admin, farmer.id)

    r = _verify(client, auth, admin, farmer.id, 'unverified')

    assert r.status_code == 200
    db.refresh(farmer)
    assert farmer.verification_status == 'unverified'
    assert client.get('/listings').json()['items'][0]['verified'] is False

def test_verifying_one_farmer_does_not_verify_another(client, db, auth, make_user, make_listing):
    chosen = make_user('chosen@test.demo', 'farmer')
    other = make_user('other@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    make_listing(chosen, title='Chosen Produce')
    make_listing(other, title='Other Produce')

    _verify(client, auth, admin, chosen.id)

    shown = {x['title']: x['verified'] for x in client.get('/listings').json()['items']}
    assert shown['Chosen Produce'] is True
    assert shown['Other Produce'] is False

def test_a_buyer_cannot_be_verified(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    buyer = make_user('buyer@test.demo', 'buyer')

    r = _verify(client, auth, admin, buyer.id)

    assert r.status_code == 422
    db.refresh(buyer)
    assert buyer.verification_status == 'unverified'

def test_an_admin_cannot_be_verified(client, db, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')
    other_admin = make_user('admin2@test.demo', 'admin')

    r = _verify(client, auth, admin, other_admin.id)

    assert r.status_code == 422
    db.refresh(other_admin)
    assert other_admin.verification_status == 'unverified'

def test_unknown_user_is_a_404(client, auth, make_user):
    admin = make_user('admin@test.demo', 'admin')

    r = _verify(client, auth, admin, 9999)

    assert r.status_code == 404

def test_bad_verification_status_is_rejected(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')

    r = _verify(client, auth, admin, farmer.id, 'gold-star')

    assert r.status_code == 422
    db.refresh(farmer)
    assert farmer.verification_status == 'unverified'

def test_non_admin_cannot_verify_anyone(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')
    buyer = make_user('buyer@test.demo', 'buyer')

    r = _verify(client, auth, buyer, farmer.id)

    assert r.status_code == 403
    db.refresh(farmer)
    assert farmer.verification_status == 'unverified'

def test_a_farmer_cannot_verify_themselves(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')

    r = _verify(client, auth, farmer, farmer.id)

    assert r.status_code == 403
    db.refresh(farmer)
    assert farmer.verification_status == 'unverified'

def test_admin_user_list_reports_verification_status(client, db, auth, make_user):
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    _verify(client, auth, admin, farmer.id)

    rows = client.get('/admin/users', headers=auth(admin)).json()

    row = next(x for x in rows if x['id'] == farmer.id)
    assert row['verification_status'] == 'verified'

def test_verification_survives_deactivation_and_reactivation(client, db, auth, make_user, make_listing):
    """Deactivating a farmer suspends their listings; it must not silently
    strip the verification an admin granted. The two are separate decisions."""
    farmer = make_user('farmer@test.demo', 'farmer')
    admin = make_user('admin@test.demo', 'admin')
    make_listing(farmer)
    _verify(client, auth, admin, farmer.id)

    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': False}, headers=auth(admin))
    client.patch(f'/admin/users/{farmer.id}/active', json={'is_active': True}, headers=auth(admin))

    db.refresh(farmer)
    assert farmer.verification_status == 'verified'
