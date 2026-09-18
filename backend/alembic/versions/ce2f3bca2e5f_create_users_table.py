"""create users table

Revision ID: ce2f3bca2e5f
Revises: 74ffb042dc2d
Create Date: 2026-09-18 15:00:00.000000

Adds the `users` table (Step 22,
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section 8.1)
-- this project's first identity/account entity. A standalone CREATE TABLE
with no interaction with any existing table and no backfill concern of its
own, since a brand-new table starts empty. `email` carries a unique index
(login lookup + uniqueness enforcement in one). `hashed_password` never
holds plaintext -- see app/core/security.py. `is_active` defaults to true;
nothing in this migration or the application yet sets it false (no
deactivation feature exists).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce2f3bca2e5f'
down_revision: Union[str, Sequence[str], None] = '74ffb042dc2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
