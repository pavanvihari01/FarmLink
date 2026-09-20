"""addresses, payment methods, and order snapshots

Adds saved delivery addresses and saved payment methods, plus two nullable
snapshot columns on orders so an order keeps showing the address and payment
label it was placed with even after the user deletes either.

Revision ID: 0003_addresses_and_payments
Revises: 0002_order_status_changed_at
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0003_addresses_and_payments'
down_revision: Union[str, None] = '0002_order_status_changed_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'addresses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('label', sa.String(length=60), nullable=False),
        sa.Column('line1', sa.String(length=200), nullable=False),
        sa.Column('line2', sa.String(length=200), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('pincode', sa.String(length=12), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_addresses_user_id', 'addresses', ['user_id'])

    op.create_table(
        'payment_methods',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('label', sa.String(length=60), nullable=False),
        sa.Column('method_type', sa.String(length=20), nullable=False),
        sa.Column('last4', sa.String(length=4), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_payment_methods_user_id', 'payment_methods', ['user_id'])

    op.add_column('orders', sa.Column('delivery_address', sa.Text(), nullable=True))
    op.add_column('orders', sa.Column('payment_label', sa.String(length=120), nullable=True))

def downgrade() -> None:
    op.drop_column('orders', 'payment_label')
    op.drop_column('orders', 'delivery_address')
    op.drop_index('ix_payment_methods_user_id', table_name='payment_methods')
    op.drop_table('payment_methods')
    op.drop_index('ix_addresses_user_id', table_name='addresses')
    op.drop_table('addresses')
