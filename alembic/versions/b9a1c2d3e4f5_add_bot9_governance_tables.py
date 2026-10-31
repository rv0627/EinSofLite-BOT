"""add bot9 governance tables

Revision ID: b9a1c2d3e4f5
Revises: 20d9d3dca089
Create Date: 2026-09-28 09:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9a1c2d3e4f5'
down_revision: Union[str, None] = 'cc62920a5ed3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Model Governance Events (Immutable Audit Log)
    op.create_table(
        'model_governance_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(), nullable=True),
        sa.Column('model_type', sa.String(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('actor', sa.String(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('previous_status', sa.String(), nullable=True),
        sa.Column('new_status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_governance_events_event_type'), 'model_governance_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_model_governance_events_model_type'), 'model_governance_events', ['model_type'], unique=False)

    # 2. Model Versions (Version Registry)
    op.create_table(
        'model_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('model_type', sa.String(), nullable=True),
        sa.Column('version', sa.String(), nullable=True),
        sa.Column('config_snapshot', sa.JSON(), nullable=True),
        sa.Column('input_data_hash', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('promoted_at', sa.DateTime(), nullable=True),
        sa.Column('retired_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_model_versions_model_type'), 'model_versions', ['model_type'], unique=False)

    # 3. Drift Monitoring Logs
    op.create_table(
        'drift_monitoring_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('model_type', sa.String(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('brier_score', sa.Float(), nullable=True),
        sa.Column('log_loss', sa.Float(), nullable=True),
        sa.Column('state_frequency_drift', sa.JSON(), nullable=True),
        sa.Column('transition_drift', sa.JSON(), nullable=True),
        sa.Column('probability_instability', sa.Float(), nullable=True),
        sa.Column('deterministic_vs_markov_delta', sa.Float(), nullable=True),
        sa.Column('drift_status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_drift_monitoring_logs_model_type'), 'drift_monitoring_logs', ['model_type'], unique=False)
    op.create_index(op.f('ix_drift_monitoring_logs_date'), 'drift_monitoring_logs', ['date'], unique=False)


def downgrade() -> None:
    op.drop_table('drift_monitoring_logs')
    op.drop_table('model_versions')
    op.drop_table('model_governance_events')
