"""add interpretation sequence column

Revision ID: 74ffb042dc2d
Revises: 2520310c3acf
Create Date: 2026-09-18 10:13:29.823028

Adds Interpretation.sequence: a globally unique, monotonically increasing
integer assigned by application code (see
app/services/interpretation/persistence.py's _next_sequence) at insert
time, used as the deterministic "current interpretation for this reading"
ordering key -- see Documentation/READING_INTEGRATION_DESIGN.md Section 7
(Resolved Q2) for why created_at alone is not a reliable tiebreak on
SQLite.

The column is added with a temporary server_default so this migration is
safe to run against a table that already has rows (SQLite requires a
default to ADD COLUMN ... NOT NULL on a non-empty table); any pre-existing
rows are then backfilled with a real, deterministic sequence (ordered by
created_at, then id, as a best-effort tiebreak for data that predates this
column) before the default is dropped and the uniqueness constraint is
added -- the constraint must come after backfill, since a table with more
than one pre-existing row would otherwise briefly violate uniqueness at
the shared default value. Every row created going forward is always
assigned an explicit value by application code; the default is only a
migration-time safety net, never relied upon afterward.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74ffb042dc2d'
down_revision: Union[str, Sequence[str], None] = '2520310c3acf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'interpretations',
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
    )

    connection = op.get_bind()
    interpretations = sa.table(
        'interpretations',
        sa.column('id', sa.Uuid()),
        sa.column('sequence', sa.Integer()),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    rows = connection.execute(
        sa.select(interpretations.c.id).order_by(
            interpretations.c.created_at, interpretations.c.id
        )
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        connection.execute(
            interpretations.update()
            .where(interpretations.c.id == row.id)
            .values(sequence=index)
        )

    with op.batch_alter_table('interpretations') as batch_op:
        batch_op.alter_column('sequence', server_default=None)
        batch_op.create_unique_constraint('uq_interpretations_sequence', ['sequence'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('interpretations') as batch_op:
        batch_op.drop_constraint('uq_interpretations_sequence', type_='unique')
        batch_op.drop_column('sequence')
