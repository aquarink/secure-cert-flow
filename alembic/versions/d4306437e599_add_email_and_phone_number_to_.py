"""add_email_and_phone_number_to_attendances

Revision ID: d4306437e599
Revises: e4b9a335e830
Create Date: 2026-08-27 15:20:36.248868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4306437e599'
down_revision: Union[str, Sequence[str], None] = 'e4b9a335e830'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('attendances', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('attendances', sa.Column('phone_number', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_attendances_email'), 'attendances', ['email'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_attendances_email'), table_name='attendances')
    op.drop_column('attendances', 'phone_number')
    op.drop_column('attendances', 'email')
