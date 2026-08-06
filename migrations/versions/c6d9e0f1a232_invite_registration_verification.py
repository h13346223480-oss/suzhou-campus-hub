"""verify invite registrations and record redemptions

Revision ID: c6d9e0f1a232
Revises: b5c8d9e0f121
Create Date: 2026-08-02 17:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "c6d9e0f1a232"
down_revision = "b5c8d9e0f121"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column("joined_via_invite", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    user = sa.table(
        "user",
        sa.column("role", sa.String()),
        sa.column("verification_status", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("joined_via_invite", sa.Boolean()),
    )
    # 生产环境普通学生只能由邀请码注册，因此现有普通学生均标记为邀请码加入。
    op.execute(
        user.update().where(user.c.role != "admin").values(joined_via_invite=True)
    )
    # 只提升仍启用的 pending 学生；停用账号和管理员完全不受影响。
    op.execute(
        user.update().where(
            sa.and_(
                user.c.role == "student",
                user.c.verification_status == "pending",
                user.c.is_active.is_(True),
            )
        ).values(verification_status="verified")
    )

    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column(
            "joined_via_invite",
            existing_type=sa.Boolean(),
            server_default=None,
        )

    op.create_table(
        "invite_redemption",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invite_code_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invite_code_id"], ["invite_code.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_invite_redemption_user_id"),
    )
    op.create_index(
        "ix_invite_redemption_invite_code_id", "invite_redemption", ["invite_code_id"], unique=False
    )
    op.create_index(
        "ix_invite_redemption_user_id", "invite_redemption", ["user_id"], unique=False
    )


def downgrade():
    op.drop_index("ix_invite_redemption_user_id", table_name="invite_redemption")
    op.drop_index("ix_invite_redemption_invite_code_id", table_name="invite_redemption")
    op.drop_table("invite_redemption")
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("joined_via_invite")
