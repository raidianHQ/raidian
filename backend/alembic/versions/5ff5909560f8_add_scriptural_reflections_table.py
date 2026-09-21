"""add scriptural_reflections table

Revision ID: 5ff5909560f8
Revises: 363f9911ef80
Create Date: 2026-09-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ff5909560f8'
down_revision: Union[str, Sequence[str], None] = '363f9911ef80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('scriptural_reflections',
    sa.Column('interpretation_id', sa.Uuid(), nullable=False),
    sa.Column('scriptural_perspective', sa.JSON(), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['interpretation_id'], ['interpretations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sequence')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('scriptural_reflections')
