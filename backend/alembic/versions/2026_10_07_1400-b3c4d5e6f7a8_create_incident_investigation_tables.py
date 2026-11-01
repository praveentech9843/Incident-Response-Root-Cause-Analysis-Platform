"""create_incident_investigation_tables

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-07 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add resolution columns to incidents table
    op.add_column('incidents', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('incidents', sa.Column('resolution_summary', sa.Text(), nullable=True))
    op.add_column('incidents', sa.Column('resolved_by', sa.String(length=128), nullable=True))
    op.add_column('incidents', sa.Column('root_cause_confirmed', sa.String(length=32), nullable=True))

    # 2. Create incident_investigations table
    op.create_table(
        'incident_investigations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('assigned_to', sa.String(length=128), nullable=True),
        sa.Column('assigned_to_name', sa.String(length=128), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='UNASSIGNED'),
        sa.Column('investigation_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incident_investigations_id'), 'incident_investigations', ['id'], unique=False)
    op.create_index(op.f('ix_incident_investigations_incident_id'), 'incident_investigations', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_investigations_status'), 'incident_investigations', ['status'], unique=False)
    op.create_index(op.f('ix_incident_investigations_assigned_to'), 'incident_investigations', ['assigned_to'], unique=False)
    op.create_index(op.f('ix_incident_investigations_created_at'), 'incident_investigations', ['created_at'], unique=False)

    # 3. Create incident_investigation_notes table
    op.create_table(
        'incident_investigation_notes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('investigation_id', sa.Integer(), nullable=False),
        sa.Column('author', sa.String(length=128), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('evidence_references', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['investigation_id'], ['incident_investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incident_investigation_notes_id'), 'incident_investigation_notes', ['id'], unique=False)
    op.create_index(op.f('ix_incident_investigation_notes_incident_id'), 'incident_investigation_notes', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_investigation_notes_investigation_id'), 'incident_investigation_notes', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_incident_investigation_notes_created_at'), 'incident_investigation_notes', ['created_at'], unique=False)

    # 4. Create incident_investigation_actions table
    op.create_table(
        'incident_investigation_actions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('investigation_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=32), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('performed_by', sa.String(length=128), nullable=False),
        sa.Column('result', sa.Text(), nullable=False),
        sa.Column('evidence_references', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['investigation_id'], ['incident_investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incident_investigation_actions_id'), 'incident_investigation_actions', ['id'], unique=False)
    op.create_index(op.f('ix_incident_investigation_actions_incident_id'), 'incident_investigation_actions', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_investigation_actions_investigation_id'), 'incident_investigation_actions', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_incident_investigation_actions_action_type'), 'incident_investigation_actions', ['action_type'], unique=False)
    op.create_index(op.f('ix_incident_investigation_actions_created_at'), 'incident_investigation_actions', ['created_at'], unique=False)

    # 5. Create incident_recommendation_reviews table
    op.create_table(
        'incident_recommendation_reviews',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('investigation_id', sa.Integer(), nullable=True),
        sa.Column('recommendation_id', sa.String(length=64), nullable=False),
        sa.Column('reviewed_by', sa.String(length=128), nullable=False),
        sa.Column('decision', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['investigation_id'], ['incident_investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incident_recommendation_reviews_id'), 'incident_recommendation_reviews', ['id'], unique=False)
    op.create_index(op.f('ix_incident_recommendation_reviews_incident_id'), 'incident_recommendation_reviews', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_recommendation_reviews_recommendation_id'), 'incident_recommendation_reviews', ['recommendation_id'], unique=False)
    op.create_index(op.f('ix_incident_recommendation_reviews_decision'), 'incident_recommendation_reviews', ['decision'], unique=False)
    op.create_index(op.f('ix_incident_recommendation_reviews_created_at'), 'incident_recommendation_reviews', ['created_at'], unique=False)

    # 6. Create incident_verification_steps table
    op.create_table(
        'incident_verification_steps',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('investigation_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('verified_by', sa.String(length=128), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('evidence_references', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['investigation_id'], ['incident_investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incident_verification_steps_id'), 'incident_verification_steps', ['id'], unique=False)
    op.create_index(op.f('ix_incident_verification_steps_incident_id'), 'incident_verification_steps', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_verification_steps_investigation_id'), 'incident_verification_steps', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_incident_verification_steps_status'), 'incident_verification_steps', ['status'], unique=False)
    op.create_index(op.f('ix_incident_verification_steps_created_at'), 'incident_verification_steps', ['created_at'], unique=False)

    # 7. Create incident_timeline_events table
    op.create_table(
        'incident_timeline_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('investigation_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('actor', sa.String(length=128), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('related_entity_type', sa.String(length=64), nullable=True),
        sa.Column('related_entity_id', sa.String(length=64), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['investigation_id'], ['incident_investigations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incident_timeline_events_id'), 'incident_timeline_events', ['id'], unique=False)
    op.create_index(op.f('ix_incident_timeline_events_incident_id'), 'incident_timeline_events', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_timeline_events_investigation_id'), 'incident_timeline_events', ['investigation_id'], unique=False)
    op.create_index(op.f('ix_incident_timeline_events_event_type'), 'incident_timeline_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_incident_timeline_events_timestamp'), 'incident_timeline_events', ['timestamp'], unique=False)


def downgrade() -> None:
    # 7. Drop incident_timeline_events
    op.drop_table('incident_timeline_events')

    # 6. Drop incident_verification_steps
    op.drop_table('incident_verification_steps')

    # 5. Drop incident_recommendation_reviews
    op.drop_table('incident_recommendation_reviews')

    # 4. Drop incident_investigation_actions
    op.drop_table('incident_investigation_actions')

    # 3. Drop incident_investigation_notes
    op.drop_table('incident_investigation_notes')

    # 2. Drop incident_investigations
    op.drop_table('incident_investigations')

    # 1. Drop columns from incidents
    op.drop_column('incidents', 'root_cause_confirmed')
    op.drop_column('incidents', 'resolved_by')
    op.drop_column('incidents', 'resolution_summary')
    op.drop_column('incidents', 'resolved_at')
