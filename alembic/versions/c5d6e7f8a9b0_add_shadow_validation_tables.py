"""add shadow validation tables

Revision ID: c5d6e7f8a9b0
Revises: b9a1c2d3e4f5
Create Date: 2026-10-06 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'b9a1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Shadow Validation Periods
    op.create_table('shadow_validation_periods',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('period_name', sa.String(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('target_end_date', sa.Date(), nullable=True),
        sa.Column('actual_end_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('trading_days_logged', sa.Integer(), nullable=True),
        sa.Column('control_model', sa.String(), nullable=True),
        sa.Column('variant_model', sa.String(), nullable=True),
        sa.Column('final_verdict', sa.String(), nullable=True),
        sa.Column('report_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('period_name')
    )

    # Shadow Daily Logs
    op.create_table('shadow_daily_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('period_id', sa.Integer(), nullable=True),
        sa.Column('trading_day', sa.Date(), nullable=True),
        sa.Column('day_number', sa.Integer(), nullable=True),
        # Control Path
        sa.Column('control_deployment_pct', sa.Float(), nullable=True),
        sa.Column('control_top20_weights', sa.JSON(), nullable=True),
        sa.Column('control_portfolio_return', sa.Float(), nullable=True),
        sa.Column('control_cumulative_return', sa.Float(), nullable=True),
        sa.Column('control_max_drawdown', sa.Float(), nullable=True),
        # Variant Path
        sa.Column('variant_deployment_pct', sa.Float(), nullable=True),
        sa.Column('variant_regime', sa.String(), nullable=True),
        sa.Column('variant_markov_modifier', sa.Float(), nullable=True),
        sa.Column('variant_top20_weights', sa.JSON(), nullable=True),
        sa.Column('variant_portfolio_return', sa.Float(), nullable=True),
        sa.Column('variant_cumulative_return', sa.Float(), nullable=True),
        sa.Column('variant_max_drawdown', sa.Float(), nullable=True),
        # Comparison
        sa.Column('return_delta', sa.Float(), nullable=True),
        sa.Column('deployment_delta', sa.Float(), nullable=True),
        sa.Column('regime_snapshot_id', sa.String(), nullable=True),
        # Markov Calibration
        sa.Column('predicted_regime_probs', sa.JSON(), nullable=True),
        sa.Column('actual_next_regime', sa.String(), nullable=True),
        # Monte Carlo Calibration
        sa.Column('mc_predicted_var95_20d', sa.Float(), nullable=True),
        sa.Column('mc_actual_20d_return', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['period_id'], ['shadow_validation_periods.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('period_id', 'trading_day', name='uq_shadow_period_day')
    )
    op.create_index(op.f('ix_shadow_daily_logs_period_id'), 'shadow_daily_logs', ['period_id'], unique=False)
    op.create_index(op.f('ix_shadow_daily_logs_trading_day'), 'shadow_daily_logs', ['trading_day'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_shadow_daily_logs_trading_day'), table_name='shadow_daily_logs')
    op.drop_index(op.f('ix_shadow_daily_logs_period_id'), table_name='shadow_daily_logs')
    op.drop_table('shadow_daily_logs')
    op.drop_table('shadow_validation_periods')
