"""reports table

Adds buyer-filed reports against listings. The farmer is denormalized onto the
row so the lock threshold can be counted without a join.

Revision ID: 0004_reports
Revises: 0003_addresses_and_payments
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004_reports'
down_revision: Union[str, None] = '0003_addresses_and_payments'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('reporter_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reported_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('listing_id', sa.Integer(), sa.ForeignKey('listings.id'), nullable=False),
        sa.Column('reason', sa.String(length=40), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('reporter_id', 'listing_id', name='uq_reports_reporter_listing'),
    )
    op.create_index('ix_reports_reporter_id', 'reports', ['reporter_id'])
    op.create_index('ix_reports_reported_user_id', 'reports', ['reported_user_id'])

def downgrade() -> None:
    op.drop_index('ix_reports_reported_user_id', table_name='reports')
    op.drop_index('ix_reports_reporter_id', table_name='reports')
    op.drop_table('reports')
