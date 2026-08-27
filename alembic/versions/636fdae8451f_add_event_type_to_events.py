"""add_event_type_to_events

Revision ID: 636fdae8451f
Revises: 020ca4d8cfa5
Create Date: 2026-08-27 14:17:28.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '636fdae8451f'
down_revision: Union[str, None] = '020ca4d8cfa5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('event_type', sa.String(length=50), server_default='general', nullable=False))


def downgrade() -> None:
    op.drop_column('events', 'event_type')
