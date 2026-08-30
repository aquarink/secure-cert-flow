"""add cert_prefix column to events table

Revision ID: dcd5477ef45a
Revises: d4bfa8875979
Create Date: 2026-08-30 04:21:40.111352

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dcd5477ef45a'
down_revision: Union[str, Sequence[str], None] = 'd4bfa8875979'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('events', sa.Column('cert_prefix', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('events', 'cert_prefix')
