"""add display_name to domains

Revision ID: e7a1c9d4b2f8
Revises: d1ed80e24fc0
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a1c9d4b2f8'
down_revision: Union[str, Sequence[str], None] = 'd1ed80e24fc0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'domains',
        sa.Column('display_name', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('domains', 'display_name')
