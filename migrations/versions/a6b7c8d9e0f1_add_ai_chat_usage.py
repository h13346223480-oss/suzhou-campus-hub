"""add ai chat usage table

Revision ID: a6b7c8d9e0f1
Revises: c8e1d2f3a4b5
Create Date: 2026-08-06 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6b7c8d9e0f1'
down_revision = 'c8e1d2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_chat_usage',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('model', sa.String(length=60), nullable=False),
    sa.Column('prompt_tokens', sa.Integer(), nullable=False),
    sa.Column('completion_tokens', sa.Integer(), nullable=False),
    sa.Column('total_tokens', sa.Integer(), nullable=False),
    sa.Column('cost', sa.Numeric(12, 6), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_chat_usage_user_id'), 'ai_chat_usage', ['user_id'], unique=False)
    op.create_index(op.f('ix_ai_chat_usage_created'), 'ai_chat_usage', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_ai_chat_usage_created'), table_name='ai_chat_usage')
    op.drop_index(op.f('ix_ai_chat_usage_user_id'), table_name='ai_chat_usage')
    op.drop_table('ai_chat_usage')
