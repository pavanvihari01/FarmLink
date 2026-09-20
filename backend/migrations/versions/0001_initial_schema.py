"""initial schema

Matches app/models/entities.py as of dispatch #1: users, categories,
listings, orders.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='buyer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('default_lifespan_hours', sa.Integer(), nullable=False),
        sa.UniqueConstraint('name', name='uq_categories_name'),
    )

    op.create_table(
        'listings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('farmer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('title', sa.String(length=140), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('image_url', sa.String(length=500), nullable=False, server_default='/images/market-harvest.png'),
        sa.Column('price_per_unit', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False, server_default='kg'),
        sa.Column('available_quantity', sa.Float(), nullable=False),
        sa.Column('harvest_time', sa.DateTime(), nullable=True),
        sa.Column('listing_time', sa.DateTime(), nullable=False),
        sa.Column('lifespan_hours', sa.Integer(), nullable=False),
        sa.Column('organic', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('bulk_available', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('location_text', sa.String(length=140), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
    )

    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('buyer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('farmer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('listing_id', sa.Integer(), sa.ForeignKey('listings.id'), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('total_amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='requested'),
        sa.Column('payment_mode', sa.String(length=30), nullable=False, server_default='demo'),
        sa.Column('payment_status', sa.String(length=20), nullable=False, server_default='simulated'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table('orders')
    op.drop_table('listings')
    op.drop_table('categories')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
