"""add moderation_note to listings

Records why an admin suspended or removed a listing. Nullable, because most
listings are never moderated.

Revision ID: 0005_listing_moderation_note
Revises: 0004_reports
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0005_listing_moderation_note'
down_revision: Union[str, None] = '0004_reports'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('listings', sa.Column('moderation_note', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('listings', 'moderation_note')
