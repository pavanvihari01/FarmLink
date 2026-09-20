"""The expiry boundary.

`freshness` floors the remaining hours for display. That floor must not decide
whether a listing has expired — a listing with thirty minutes left reports zero
whole hours, but it is not expired, and treating it as such hides live produce
from the marketplace an hour early.

Kept apart from test_freshness.py so the boundary case is not mistaken for one
of the ordinary Fresh/Expired fixtures.
"""
from datetime import datetime, timedelta

from app.services.freshness import freshness

def _listing(**over):
    fields = {
        'expires_at': datetime.utcnow() + timedelta(hours=2),
        'harvest_time': datetime.utcnow(),
        'listing_time': datetime.utcnow(),
        'lifespan_hours': 96,
    }
    fields.update(over)
    return type('L', (), fields)()

def test_thirty_minutes_left_is_not_expired():
    status, hours = freshness(_listing(expires_at=datetime.utcnow() + timedelta(minutes=30)))

    # Floored to zero whole hours, but still sellable.
    assert hours == 0
    assert status == 'Expiring'

def test_exactly_expired_is_expired():
    status, hours = freshness(_listing(expires_at=datetime.utcnow() - timedelta(seconds=1)))

    assert hours == 0
    assert status == 'Expired'

def test_just_under_an_hour_left_is_not_expired():
    status, hours = freshness(_listing(expires_at=datetime.utcnow() + timedelta(minutes=59)))

    assert hours == 0
    assert status == 'Expiring'
