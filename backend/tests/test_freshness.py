from datetime import datetime, timedelta
from types import SimpleNamespace
from app.services.freshness import freshness
def test_fresh_listing():
    listing=SimpleNamespace(harvest_time=datetime.utcnow()-timedelta(hours=10),listing_time=datetime.utcnow(),lifespan_hours=96)
    assert freshness(listing)[0]=='Fresh'
def test_expired_listing():
    listing=SimpleNamespace(harvest_time=datetime.utcnow()-timedelta(hours=30),listing_time=datetime.utcnow(),lifespan_hours=24)
    assert freshness(listing)[0]=='Expired'
