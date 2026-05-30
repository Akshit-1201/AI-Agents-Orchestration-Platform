"""channel_session history (lightweight chat memory)

Revision ID: f3a9c2b7d1e4
Revises: d455a9785e29
Create Date: 2026-05-30 12:40:00.000000

Adds `channel_sessions.history`: a capped JSON list of {"role", "content"} turns giving
each external chat a lightweight rolling conversation memory, injected into every run so
the bound workflow remembers earlier messages. Nullable (existing sessions start empty).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401 -- autogenerate emits sqlmodel.sql.sqltypes.*


# revision identifiers, used by Alembic.
revision: str = 'f3a9c2b7d1e4'
down_revision: Union[str, None] = 'd455a9785e29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('channel_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('history', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('channel_sessions', schema=None) as batch_op:
        batch_op.drop_column('history')
