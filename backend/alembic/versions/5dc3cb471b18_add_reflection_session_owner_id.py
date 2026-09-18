"""add reflection_session owner_id

Revision ID: 5dc3cb471b18
Revises: ce2f3bca2e5f
Create Date: 2026-09-18 15:05:00.000000

Adds ReflectionSession.owner_id (Step 22,
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section
8.2) -- the ownership anchor for a Reading and everything beneath it
(CardDraw, Interpretation), placed on ReflectionSession rather than
Reading per Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md Section 2.5.

Added nullable, with no server_default, and with no backfill step: unlike
`74ffb042dc2d` (Interpretation.sequence), no pre-existing row needs to
satisfy a NOT NULL requirement here, because this repository has no
persistent development or production data (every existing
ReflectionSession/Reading row is transient, per-test fixture data,
re-verified in
Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section
4.3). A future migration may transition this column to NOT NULL once a
Reading/ReflectionSession-creation API exists that always supplies an
owner -- not designed or performed here.

op.batch_alter_table is used for the foreign-key addition specifically
because SQLite cannot add a foreign-key constraint to an existing table
via a plain ALTER TABLE -- the same reason `74ffb042dc2d` already uses
batch_alter_table for its own constraint addition.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5dc3cb471b18'
down_revision: Union[str, Sequence[str], None] = 'ce2f3bca2e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'reflection_sessions',
        sa.Column('owner_id', sa.Uuid(), nullable=True),
    )
    op.create_index(
        'ix_reflection_sessions_owner_id', 'reflection_sessions', ['owner_id']
    )
    with op.batch_alter_table('reflection_sessions') as batch_op:
        batch_op.create_foreign_key(
            'fk_reflection_sessions_owner_id_users',
            'users', ['owner_id'], ['id'], ondelete='CASCADE',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('reflection_sessions') as batch_op:
        batch_op.drop_constraint('fk_reflection_sessions_owner_id_users', type_='foreignkey')
    op.drop_index('ix_reflection_sessions_owner_id', table_name='reflection_sessions')
    op.drop_column('reflection_sessions', 'owner_id')
