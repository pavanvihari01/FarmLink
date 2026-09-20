"""delivery: address coordinates, delivery method, and delivery status

Adds optional coordinates to saved addresses, plus five columns on orders so a
delivery can be routed and tracked independently of the order's own
requested/accepted/completed lifecycle.

delivery_method gets a server default of 'pickup' so existing rows are valid
without a backfill — none of them recorded a delivery intention, and pickup is
the honest reading. delivery_status stays null for those rows, which is correct:
a pickup has no delivery to track.

Revision ID: 0008_delivery
Revises: 0007_subscriptions
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0008_delivery'
down_revision: Union[str, None] = '0007_subscriptions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('addresses', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('addresses', sa.Column('longitude', sa.Float(), nullable=True))

    op.add_column('orders', sa.Column('delivery_method', sa.String(length=20), nullable=False, server_default='pickup'))
    op.add_column('orders', sa.Column('delivery_latitude', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('delivery_longitude', sa.Float(), nullable=True))
    op.add_column('orders', sa.Column('delivery_status', sa.String(length=30), nullable=True))
    op.add_column('orders', sa.Column('delivery_note', sa.Text(), nullable=True))
    op.create_index('ix_orders_delivery_status', 'orders', ['delivery_status'])

def downgrade() -> None:
    op.drop_index('ix_orders_delivery_status', table_name='orders')
    op.drop_column('orders', 'delivery_note')
    op.drop_column('orders', 'delivery_status')
    op.drop_column('orders', 'delivery_longitude')
    op.drop_column('orders', 'delivery_latitude')
    op.drop_column('orders', 'delivery_method')
    op.drop_column('addresses', 'longitude')
    op.drop_column('addresses', 'latitude')
