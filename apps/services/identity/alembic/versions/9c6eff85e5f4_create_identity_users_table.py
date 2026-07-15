"""create identity users table

Revision ID: 9c6eff85e5f4
Revises:
Create Date: 2026-07-14 02:58:40.382017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c6eff85e5f4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='identity'
    )
    op.create_index(op.f('ix_identity_users_email'), 'users', ['email'], unique=True, schema='identity')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_identity_users_email'), table_name='users', schema='identity')
    op.drop_table('users', schema='identity')
