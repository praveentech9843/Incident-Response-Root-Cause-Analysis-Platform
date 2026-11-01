"""create_incident_rca_analyses_table

Revision ID: e1a2b3c4d5e6
Revises: d0fb7f3d3149
Create Date: 2026-10-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e1a2b3c4d5e6'
down_revision: Union[str, None] = 'd0fb7f3d3149'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'incident_rca_analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.String(length=64), nullable=False),
        sa.Column('analysis_status', sa.String(length=32), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('confidence_level', sa.String(length=32), nullable=True),
        sa.Column('hypotheses', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('evidence_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('limitations', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_id', name='uq_incident_rca_analyses_analysis_id')
    )
    op.create_index(op.f('ix_incident_rca_analyses_id'), 'incident_rca_analyses', ['id'], unique=False)
    op.create_index(op.f('ix_incident_rca_analyses_incident_id'), 'incident_rca_analyses', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_rca_analyses_analysis_id'), 'incident_rca_analyses', ['analysis_id'], unique=True)
    op.create_index(op.f('ix_incident_rca_analyses_analysis_status'), 'incident_rca_analyses', ['analysis_status'], unique=False)
    op.create_index(op.f('ix_incident_rca_analyses_created_at'), 'incident_rca_analyses', ['created_at'], unique=False)
    op.create_index('ix_incident_rca_analyses_incident_created', 'incident_rca_analyses', ['incident_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_incident_rca_analyses_incident_created', table_name='incident_rca_analyses')
    op.drop_index(op.f('ix_incident_rca_analyses_created_at'), table_name='incident_rca_analyses')
    op.drop_index(op.f('ix_incident_rca_analyses_analysis_status'), table_name='incident_rca_analyses')
    op.drop_index(op.f('ix_incident_rca_analyses_analysis_id'), table_name='incident_rca_analyses')
    op.drop_index(op.f('ix_incident_rca_analyses_incident_id'), table_name='incident_rca_analyses')
    op.drop_index(op.f('ix_incident_rca_analyses_id'), table_name='incident_rca_analyses')
    op.drop_table('incident_rca_analyses')
