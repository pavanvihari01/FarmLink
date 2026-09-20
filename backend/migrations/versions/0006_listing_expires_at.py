"""add expires_at to listings

Stores (harvest_time or listing_time) + lifespan_hours so sorting by freshness
and filtering out expired listings do not have to recompute the base time on
every query. Indexed because both operations are common.

The backfill runs in Python rather than SQL. SQLite wants
datetime(base, '+48 hours') and PostgreSQL wants base + interval '48 hours',
and a migration that only works on one of them is worse than a slow one that
works on both.

Revision ID: 0006_listing_expires_at
Revises: 0005_listing_moderation_note
Create Date: 2026-09-19

"""
from datetime import datetime, timedelta
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0006_listing_expires_at'
down_revision: Union[str, None] = '0005_listing_moderation_note'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('listings', sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.create_index('ix_listings_expires_at', 'listings', ['expires_at'])

    bind = op.get_bind()
    rows = bind.execute(
        sa.text('SELECT id, harvest_time, listing_time, lifespan_hours FROM listings')
    ).fetchall()

    for row in rows:
        base = row.harvest_time or row.listing_time
        if base is None:
            continue
        # SQLite hands back datetimes as strings through raw text() queries.
        if isinstance(base, str):
            base = datetime.fromisoformat(base)
        bind.execute(
            sa.text('UPDATE listings SET expires_at = :expires WHERE id = :id'),
            {'expires': base + timedelta(hours=row.lifespan_hours), 'id': row.id},
        )

def downgrade() -> None:
    op.drop_index('ix_listings_expires_at', table_name='listings')
    op.drop_column('listings', 'expires_at')
