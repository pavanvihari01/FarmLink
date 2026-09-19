from datetime import datetime, timedelta
def freshness(listing, now: datetime | None = None):
    now = now or datetime.utcnow()
    base = listing.harvest_time or listing.listing_time
    remaining = max(0, int((base + timedelta(hours=listing.lifespan_hours) - now).total_seconds() // 3600))
    pct = remaining / listing.lifespan_hours if listing.lifespan_hours else 0
    status = 'Fresh' if pct > .6 else 'Use Soon' if pct >= .3 else 'Expiring' if remaining > 0 else 'Expired'
    return status, remaining
