"""add is_paid column to papers table

Revision ID: d4bfa8875979
Revises: df46c6f8ba51
Create Date: 2026-08-30 04:12:48.197369

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4bfa8875979'
down_revision: Union[str, Sequence[str], None] = 'df46c6f8ba51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('papers', sa.Column('is_paid', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('papers', 'is_paid')
