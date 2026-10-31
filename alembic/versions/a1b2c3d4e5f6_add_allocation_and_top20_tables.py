"""add allocation_results and top20_portfolio tables

Revision ID: a1b2c3d4e5f6
Revises: d0fd013f0cc6
Create Date: 2026-07-02 08:25:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f242995bd28b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bot 4 - Allocation Results
    op.create_table(
        'allocation_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol_id', sa.String(), sa.ForeignKey('symbol_master.symbol_id'), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('ein_score', sa.Float(), nullable=True),
        sa.Column('raw_weight', sa.Float(), nullable=True),
        sa.Column('risk_adjusted_weight', sa.Float(), nullable=True),
        sa.Column('position_size_pct', sa.Float(), nullable=True),
        sa.Column('sector', sa.String(), nullable=True),
        sa.Column('volatility_30d', sa.Float(), nullable=True),
        sa.Column('risk_flag', sa.String(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_allocation_results_date', 'allocation_results', ['date'])

    # Bot 5 - Top 20 Portfolio
    op.create_table(
        'top20_portfolio',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol_id', sa.String(), sa.ForeignKey('symbol_master.symbol_id'), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('final_rank', sa.Integer(), nullable=True),
        sa.Column('allocation_pct', sa.Float(), nullable=True),
        sa.Column('allocation_amount', sa.Float(), nullable=True),
        sa.Column('ein_score', sa.Float(), nullable=True),
        sa.Column('risk_category', sa.String(), nullable=True),
        sa.Column('inclusion_reason', sa.String(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_top20_portfolio_date', 'top20_portfolio', ['date'])


def downgrade() -> None:
    op.drop_index('ix_top20_portfolio_date', table_name='top20_portfolio')
    op.drop_table('top20_portfolio')
    op.drop_index('ix_allocation_results_date', table_name='allocation_results')
    op.drop_table('allocation_results')
