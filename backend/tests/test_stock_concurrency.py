"""Stock reservation against a stale read.

The old flow read `available_quantity`, checked it in Python, then decremented
and committed. Two requests that both read 10 available would both pass the
check and both decrement — whichever committed second won, and the other order
was confirmed against stock that no longer existed.

Reserving is now a single guarded UPDATE, so the database picks the winner and
the loser sees rowcount 0. These tests exercise that guard directly: they load
a listing, change the row behind the session's back, and prove the reserve
refuses.

`reopen_order` and `generate_due_cycles` call the same helper. Their race paths
are not reproduced here — TestClient runs requests sequentially and the
in-memory engine hands every session the same connection, so there is no real
concurrency to arrange. Those two call sites are covered by the existing
reopen and subscription-cycle tests instead.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from app.api.routes import _reserve_stock
from app.models.entities import Listing

def _stored_quantity(db, listing_id):
    """The value in the row, not the one the session has cached."""
    return db.scalar(select(Listing.available_quantity).where(Listing.id == listing_id))

def test_reserve_takes_stock_off(db, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, quantity=10)

    _reserve_stock(db, listing, 4)

    assert _stored_quantity(db, listing.id) == 6

def test_reserve_refreshes_the_loaded_object(db, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, quantity=10)

    _reserve_stock(db, listing, 4)

    # Without the refresh the caller would read the pre-reserve value, and
    # create_order reports that value straight back to the buyer.
    assert listing.available_quantity == 6

def test_reserve_refuses_more_than_is_available(db, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, quantity=3)

    with pytest.raises(HTTPException) as caught:
        _reserve_stock(db, listing, 10)

    assert caught.value.status_code == 422
    assert _stored_quantity(db, listing.id) == 3

def test_reserve_allows_exactly_the_whole_stock_once(db, make_user, make_listing):
    """The boundary. Taking all of it once is fine; taking it twice is not."""
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, quantity=5)

    _reserve_stock(db, listing, 5)
    assert _stored_quantity(db, listing.id) == 0

    with pytest.raises(HTTPException) as caught:
        _reserve_stock(db, listing, 5)
    assert caught.value.status_code == 422

def test_reserve_guards_against_a_stale_read(db, make_user, make_listing):
    """The bug this dispatch exists to fix.

    The listing is loaded with 10 available. The row is then changed to 2 out
    from under it — which is what a concurrent order committing looks like from
    this request's point of view. The loaded object still says 10, so the old
    Python check would have passed. The guarded UPDATE re-checks against the row
    and refuses.

    Raw SQL on purpose: an ORM-issued UPDATE would synchronise the session's
    copy, and the staleness is the whole point.
    """
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, quantity=10)

    db.execute(text('UPDATE listings SET available_quantity = 2 WHERE id = :id'), {'id': listing.id})

    assert listing.available_quantity == 10  # stale, and that is the setup

    with pytest.raises(HTTPException) as caught:
        _reserve_stock(db, listing, 8)

    assert caught.value.status_code == 422
    assert _stored_quantity(db, listing.id) == 2

def test_reserve_refuses_a_listing_that_is_no_longer_active(db, make_user, make_listing):
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, quantity=10)

    db.execute(text("UPDATE listings SET status = 'suspended' WHERE id = :id"), {'id': listing.id})

    with pytest.raises(HTTPException) as caught:
        _reserve_stock(db, listing, 1)

    assert caught.value.status_code == 422
    assert _stored_quantity(db, listing.id) == 10

def test_two_reserves_cannot_both_take_the_last_of_a_scarce_listing(db, make_user, make_listing):
    """Two callers each want 6 of 10.

    Sequentially the second must fail. The guarded UPDATE is what makes the
    concurrent case behave the same way rather than both succeeding.
    """
    farmer = make_user('farmer@test.demo', 'farmer')
    listing = make_listing(farmer, quantity=10)

    _reserve_stock(db, listing, 6)

    with pytest.raises(HTTPException):
        _reserve_stock(db, listing, 6)

    assert _stored_quantity(db, listing.id) == 4
