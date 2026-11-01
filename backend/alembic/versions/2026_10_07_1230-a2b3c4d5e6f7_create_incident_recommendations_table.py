"""create_incident_recommendations_table

Revision ID: a2b3c4d5e6f7
Revises: e1a2b3c4d5e6
Create Date: 2026-10-07 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'e1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'incident_recommendations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recommendation_id', sa.String(length=64), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('rca_analysis_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('supporting_evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('confidence_level', sa.String(length=16), nullable=False),
        sa.Column('risk_level', sa.String(length=16), nullable=False, server_default='LOW'),
        sa.Column('expected_impact', sa.Text(), nullable=False),
        sa.Column('prerequisites', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('verification_steps', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PROPOSED'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rca_analysis_id'], ['incident_rca_analyses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recommendation_id', name='uq_incident_recommendations_recommendation_id')
    )
    op.create_index(op.f('ix_incident_recommendations_id'), 'incident_recommendations', ['id'], unique=False)
    op.create_index(op.f('ix_incident_recommendations_recommendation_id'), 'incident_recommendations', ['recommendation_id'], unique=True)
    op.create_index(op.f('ix_incident_recommendations_incident_id'), 'incident_recommendations', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_recommendations_rca_analysis_id'), 'incident_recommendations', ['rca_analysis_id'], unique=False)
    op.create_index(op.f('ix_incident_recommendations_type'), 'incident_recommendations', ['type'], unique=False)
    op.create_index(op.f('ix_incident_recommendations_status'), 'incident_recommendations', ['status'], unique=False)
    op.create_index(op.f('ix_incident_recommendations_created_at'), 'incident_recommendations', ['created_at'], unique=False)
    op.create_index('ix_incident_recommendations_incident_created', 'incident_recommendations', ['incident_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_incident_recommendations_incident_created', table_name='incident_recommendations')
    op.drop_index(op.f('ix_incident_recommendations_created_at'), table_name='incident_recommendations')
    op.drop_index(op.f('ix_incident_recommendations_status'), table_name='incident_recommendations')
    op.drop_index(op.f('ix_incident_recommendations_type'), table_name='incident_recommendations')
    op.drop_index(op.f('ix_incident_recommendations_rca_analysis_id'), table_name='incident_recommendations')
    op.drop_index(op.f('ix_incident_recommendations_incident_id'), table_name='incident_recommendations')
    op.drop_index(op.f('ix_incident_recommendations_recommendation_id'), table_name='incident_recommendations')
    op.drop_index(op.f('ix_incident_recommendations_id'), table_name='incident_recommendations')
    op.drop_table('incident_recommendations')
