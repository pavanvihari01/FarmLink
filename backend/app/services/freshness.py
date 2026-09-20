from datetime import datetime, timedelta

def freshness(listing, now: datetime | None = None):
    """Status label and remaining hours for a listing.

    Prefers the stored `expires_at` column so the sort/filter path and the
    display path cannot drift. Falls back to computing it from `harvest_time` /
    `listing_time` plus `lifespan_hours`, which keeps this usable on plain
    objects that have no such column — including the freshness tests, which
    build SimpleNamespace fixtures.
    """
    now = now or datetime.utcnow()
    expires = getattr(listing, 'expires_at', None)
    if expires is None:
        base = listing.harvest_time or listing.listing_time
        expires = base + timedelta(hours=listing.lifespan_hours)
    seconds_left = (expires - now).total_seconds()
    # Floored for display only. Expiry is decided by the timestamp: a listing
    # with thirty minutes left floors to zero whole hours, but it has not
    # expired, and calling it Expired would hide live produce from the
    # marketplace an hour early.
    remaining = max(0, int(seconds_left // 3600))
    pct = remaining / listing.lifespan_hours if listing.lifespan_hours else 0
    if seconds_left <= 0:
        status = 'Expired'
    elif pct > .6:
        status = 'Fresh'
    elif pct >= .3:
        status = 'Use Soon'
    else:
        status = 'Expiring'
    return status, remaining
