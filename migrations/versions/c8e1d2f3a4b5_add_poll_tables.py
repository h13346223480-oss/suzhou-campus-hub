"""add poll tables

Revision ID: c8e1d2f3a4b5
Revises: b2d4f6a8c0e1
Create Date: 2026-08-05 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c8e1d2f3a4b5'
down_revision = 'b2d4f6a8c0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('poll',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_open', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['user.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('poll_option',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('poll_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=False),
    sa.Column('image_path', sa.String(length=255), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['poll_id'], ['poll.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_poll_option_poll_id'), 'poll_option', ['poll_id'], unique=False)
    op.create_table('vote',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('poll_id', sa.Integer(), nullable=False),
    sa.Column('option_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['option_id'], ['poll_option.id']),
    sa.ForeignKeyConstraint(['poll_id'], ['poll.id']),
    sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('poll_id', 'user_id', name='uq_vote_poll_user')
    )
    op.create_index(op.f('ix_vote_option_id'), 'vote', ['option_id'], unique=False)
    op.create_index(op.f('ix_vote_poll_id'), 'vote', ['poll_id'], unique=False)
    op.create_index(op.f('ix_vote_user_id'), 'vote', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_vote_user_id'), table_name='vote')
    op.drop_index(op.f('ix_vote_poll_id'), table_name='vote')
    op.drop_index(op.f('ix_vote_option_id'), table_name='vote')
    op.drop_table('vote')
    op.drop_index(op.f('ix_poll_option_poll_id'), table_name='poll_option')
    op.drop_table('poll_option')
    op.drop_table('poll')
