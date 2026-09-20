"""add status_changed_at to orders

The buyer rejection cooldown needs to know when an order was rejected, not
just when it was created. Backfills existing rows with the current timestamp
via a server default, which is safe because no order can currently be in a
terminal state (nothing sets one).

Revision ID: 0002_order_status_changed_at
Revises: 0001_initial
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0002_order_status_changed_at'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        'orders',
        sa.Column(
            'status_changed_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
    )

def downgrade() -> None:
    op.drop_column('orders', 'status_changed_at')
