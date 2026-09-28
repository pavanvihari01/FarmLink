"""farmer verification status

Adds users.verification_status so the "Verified farmer" badge reflects an
admin decision instead of `role == 'farmer'`.

That expression was a tautology. Only farmers can create listings, so
`verified` was true on every listing in the marketplace. A badge that is
always on carries no information, and it asserted something the platform
never checked.

Two states, not three. Both are reachable — an admin moves a farmer between
them. A 'pending' state would need a farmer-facing request flow before
anything could enter it, so adding it now would put a value in the schema
that no code path can produce.

The server default is 'unverified' for existing rows. Defaulting to
'verified' would make the badge true for everyone again, which is the bug
this migration exists to fix.

Revision ID: 0011_user_verification
Revises: 0010_subscription_delivery
Create Date: 2026-09-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0011_user_verification'
down_revision: Union[str, None] = '0010_subscription_delivery'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'verification_status',
            sa.String(20),
            nullable=False,
            server_default='unverified',
        ),
    )

def downgrade() -> None:
    op.drop_column('users', 'verification_status')
