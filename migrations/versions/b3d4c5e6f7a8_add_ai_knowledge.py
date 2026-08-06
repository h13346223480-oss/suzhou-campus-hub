"""add ai knowledge table

Revision ID: b3d4c5e6f7a8
Revises: a6b7c8d9e0f1
Create Date: 2026-08-06 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3d4c5e6f7a8'
down_revision = 'a6b7c8d9e0f1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_knowledge',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('keywords', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_knowledge_updated'), 'ai_knowledge', ['updated_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_ai_knowledge_updated'), table_name='ai_knowledge')
    op.drop_table('ai_knowledge')
