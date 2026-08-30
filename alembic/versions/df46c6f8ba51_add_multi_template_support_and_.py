"""add multi template support and certificate template link

Revision ID: df46c6f8ba51
Revises: d4306437e599
Create Date: 2026-08-30 03:46:59.880849

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df46c6f8ba51'
down_revision: Union[str, Sequence[str], None] = 'd4306437e599'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for multi-template support."""
    # 1. Add columns to templates table
    op.add_column('templates', sa.Column('name', sa.String(length=100), server_default='Template Utama', nullable=False))
    op.add_column('templates', sa.Column('role_target', sa.String(length=100), server_default='ALL', nullable=False))
    op.add_column('templates', sa.Column('is_default', sa.Boolean(), server_default=sa.true(), nullable=False))

    # 2. Re-create index on templates(event_id) as non-unique
    op.drop_index('ix_templates_event_id', table_name='templates')
    op.create_index('ix_templates_event_id', 'templates', ['event_id'], unique=False)

    # 3. Add optional template_id foreign key to certificates
    op.add_column('certificates', sa.Column('template_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_certificates_template_id', 'certificates', 'templates', ['template_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_certificates_template_id', 'certificates', ['template_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_certificates_template_id', table_name='certificates')
    op.drop_constraint('fk_certificates_template_id', 'certificates', type_='foreignkey')
    op.drop_column('certificates', 'template_id')

    op.drop_index('ix_templates_event_id', table_name='templates')
    op.create_index('ix_templates_event_id', 'templates', ['event_id'], unique=True)

    op.drop_column('templates', 'is_default')
    op.drop_column('templates', 'role_target')
    op.drop_column('templates', 'name')
