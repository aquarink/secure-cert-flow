"""add_is_cert_open_to_events

Revision ID: e4b9a335e830
Revises: 636fdae8451f
Create Date: 2026-08-27 14:41:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4b9a335e830'
down_revision: Union[str, None] = '636fdae8451f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('is_cert_open', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('events', 'is_cert_open')
