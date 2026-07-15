"""add cover_image_url to books

Revision ID: 4f1b9c2d7a3e
Revises: 0ac3e93a0a9e
Create Date: 2026-07-14 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f1b9c2d7a3e'
down_revision: Union[str, Sequence[str], None] = '0ac3e93a0a9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'books',
        sa.Column('cover_image_url', sa.String(length=500), nullable=True),
        schema='catalog',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('books', 'cover_image_url', schema='catalog')
