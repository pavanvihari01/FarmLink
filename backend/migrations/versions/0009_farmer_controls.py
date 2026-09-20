"""farmer listing controls and report resolution

Two columns behind dispatch #15's fixes:

  * listings.suspended_by_deactivation — lets reactivating a farmer restore
    exactly the listings the deactivation suspended, leaving anything an admin
    suspended by hand alone.
  * reports.resolution_note — free text an admin records when closing a report.

Server defaults keep existing rows valid without a backfill: no listing was
suspended by a deactivation that did not exist, and no report has been resolved.

Revision ID: 0009_farmer_controls
Revises: 0008_delivery
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0009_farmer_controls'
down_revision: Union[str, None] = '0008_delivery'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        'listings',
        sa.Column('suspended_by_deactivation', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('reports', sa.Column('resolution_note', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('reports', 'resolution_note')
    op.drop_column('listings', 'suspended_by_deactivation')
