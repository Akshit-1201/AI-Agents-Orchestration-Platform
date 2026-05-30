"""web chat sessions (multi-turn conversations per workflow)

Revision ID: b7c4e1f29a3d
Revises: f3a9c2b7d1e4
Create Date: 2026-05-30 15:10:00.000000

Adds `chat_sessions` (a durable web conversation bound to one workflow) and `runs.chat_id`
(links each chat turn to its session). Deleting a workflow cascades its chats; deleting a
chat cascades its runs (and each run's messages/events).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401 -- autogenerate emits sqlmodel.sql.sqltypes.*


# revision identifiers, used by Alembic.
revision: str = 'b7c4e1f29a3d'
down_revision: Union[str, None] = 'f3a9c2b7d1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('chat_sessions', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_chat_sessions_workflow_id'), ['workflow_id'], unique=False
        )

    with op.batch_alter_table('runs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('chat_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_runs_chat_id'), ['chat_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_runs_chat_id', 'chat_sessions', ['chat_id'], ['id'], ondelete='CASCADE'
        )


def downgrade() -> None:
    with op.batch_alter_table('runs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_runs_chat_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_runs_chat_id'))
        batch_op.drop_column('chat_id')

    with op.batch_alter_table('chat_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_sessions_workflow_id'))
    op.drop_table('chat_sessions')
