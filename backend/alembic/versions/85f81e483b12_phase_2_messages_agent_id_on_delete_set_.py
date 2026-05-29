"""phase 2: messages.agent_id ON DELETE SET NULL

Revision ID: 85f81e483b12
Revises: 09ebec4df48c
Create Date: 2026-05-29 11:04:14.951636

Deleting an agent should preserve historical messages and clear their attribution,
rather than being blocked or erroring. SQLite can't ALTER a constraint, so batch mode
recreates the table; a naming_convention lets us target the unnamed agent_id FK while
preserving the run_id CASCADE FK.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401 -- autogenerate emits sqlmodel.sql.sqltypes.* (e.g. AutoString)


# revision identifiers, used by Alembic.
revision: str = '85f81e483b12'
down_revision: Union[str, None] = '09ebec4df48c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Names unnamed reflected FKs deterministically so we can drop the right one.
_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    with op.batch_alter_table("messages", schema=None, naming_convention=_NAMING) as batch_op:
        batch_op.drop_constraint("fk_messages_agent_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_messages_agent_id", "agents", ["agent_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("messages", schema=None, naming_convention=_NAMING) as batch_op:
        batch_op.drop_constraint("fk_messages_agent_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_messages_agent_id", "agents", ["agent_id"], ["id"]
        )
