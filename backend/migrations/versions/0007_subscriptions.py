"""subscriptions and subscription cycles

Adds the two tables behind recurring produce boxes, plus a nullable
orders.subscription_id so a generated order can be traced back to the cycle
that produced it.

No data backfill is needed: orders.subscription_id is nullable and every
existing order predates the feature.

Revision ID: 0007_subscriptions
Revises: 0006_listing_expires_at
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0007_subscriptions'
down_revision: Union[str, None] = '0006_listing_expires_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('buyer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('farmer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False, server_default='kg'),
        sa.Column('frequency_days', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('next_cycle_at', sa.DateTime(), nullable=False),
        sa.Column('delivery_address', sa.Text(), nullable=False),
        sa.Column('payment_label', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_subscriptions_buyer_id', 'subscriptions', ['buyer_id'])
    op.create_index('ix_subscriptions_farmer_id', 'subscriptions', ['farmer_id'])
    op.create_index('ix_subscriptions_next_cycle_at', 'subscriptions', ['next_cycle_at'])

    op.create_table(
        'subscription_cycles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('subscriptions.id'), nullable=False),
        sa.Column('scheduled_for', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('subscription_id', 'scheduled_for', name='uq_cycles_subscription_scheduled'),
    )
    op.create_index('ix_subscription_cycles_subscription_id', 'subscription_cycles', ['subscription_id'])

    op.add_column('orders', sa.Column('subscription_id', sa.Integer(), nullable=True))
    op.create_index('ix_orders_subscription_id', 'orders', ['subscription_id'])

def downgrade() -> None:
    op.drop_index('ix_orders_subscription_id', table_name='orders')
    op.drop_column('orders', 'subscription_id')
    op.drop_index('ix_subscription_cycles_subscription_id', table_name='subscription_cycles')
    op.drop_table('subscription_cycles')
    op.drop_index('ix_subscriptions_next_cycle_at', table_name='subscriptions')
    op.drop_index('ix_subscriptions_farmer_id', table_name='subscriptions')
    op.drop_index('ix_subscriptions_buyer_id', table_name='subscriptions')
    op.drop_table('subscriptions')
