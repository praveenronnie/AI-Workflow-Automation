"""add report_intents table and form_schemas.scanned_payload

Revision ID: a1b2c3d4e5f6
Revises: f0c6e9ac7f62
Create Date: 2026-08-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f0c6e9ac7f62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Persist per-section form intents + status, keyed by report.
    op.create_table(
        'report_intents',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('report_id', sa.String(length=36), sa.ForeignKey('reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('section_id', sa.String(length=255), nullable=False),
        sa.Column('section_name', sa.String(length=255), nullable=True),
        sa.Column('field_count', sa.Integer(), nullable=True),
        sa.Column('intent', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('report_id', 'section_id', name='uq_report_intent_section'),
    )
    op.create_index('ix_report_intents_report_id', 'report_intents', ['report_id'])

    # Store the scanned payload with the form schema (submitted at scan time).
    op.add_column('form_schemas', sa.Column('scanned_payload', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('form_schemas', 'scanned_payload')
    op.drop_index('ix_report_intents_report_id', table_name='report_intents')
    op.drop_table('report_intents')
