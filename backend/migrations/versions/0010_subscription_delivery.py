"""subscription delivery coordinates

Subscriptions recorded a delivery_address string but no coordinates, so the
order that a due cycle generated could not say where it was going. Those orders
fell through to the orders table's server default of 'pickup' — the subscription
page said "delivering to" while the order it produced was a collection.

Two nullable columns, mirroring addresses and orders. A subscription without a
pin still generates a delivery order; it simply lands in the farmer's
unroutable bucket rather than on the suggested route.

Revision ID: 0010_subscription_delivery
Revises: 0009_farmer_controls
Create Date: 2026-09-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0010_subscription_delivery'
down_revision: Union[str, None] = '0009_farmer_controls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('subscriptions', sa.Column('delivery_latitude', sa.Float(), nullable=True))
    op.add_column('subscriptions', sa.Column('delivery_longitude', sa.Float(), nullable=True))

def downgrade() -> None:
    op.drop_column('subscriptions', 'delivery_longitude')
    op.drop_column('subscriptions', 'delivery_latitude')
