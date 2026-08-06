"""expand survey result processing

Revision ID: a4b7c8d9e010
Revises: f1fa31601f68
Create Date: 2026-08-02 15:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "a4b7c8d9e010"
down_revision = "f1fa31601f68"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("survey_question") as batch_op:
        batch_op.add_column(
            sa.Column("is_contact_info", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    question = sa.table(
        "survey_question",
        sa.column("title", sa.String()),
        sa.column("is_contact_info", sa.Boolean()),
    )
    op.execute(
        question.update()
        .where(
            sa.or_(
                question.c.title.like("%联系方式%"),
                question.c.title.like("%微信%"),
                question.c.title.like("%手机号%"),
                question.c.title.like("%邮箱%"),
                question.c.title.like("%QQ%"),
            )
        )
        .values(is_contact_info=True)
    )

    with op.batch_alter_table("survey_response") as batch_op:
        batch_op.add_column(
            sa.Column("validity_status", sa.String(length=20), nullable=False, server_default="valid")
        )
        batch_op.create_index("ix_survey_response_validity_status", ["validity_status"], unique=False)

    response = sa.table(
        "survey_response",
        sa.column("is_valid", sa.Boolean()),
        sa.column("validity_status", sa.String()),
    )
    op.execute(response.update().where(response.c.is_valid.is_(False)).values(validity_status="invalid"))

    op.create_table(
        "survey_answer_tag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("answer_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(length=40), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["survey_answer.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.UniqueConstraint("answer_id", "tag", name="uq_survey_answer_tag"),
    )
    op.create_index("idx_survey_answer_tag_value", "survey_answer_tag", ["tag"], unique=False)

    op.create_table(
        "survey_response_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), nullable=False),
        sa.Column("response_id", sa.Integer()),
        sa.Column("actor_id", sa.Integer()),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("previous_status", sa.String(length=20)),
        sa.Column("new_status", sa.String(length=20)),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["survey_id"], ["survey.id"]),
        sa.ForeignKeyConstraint(["response_id"], ["survey_response.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"]),
    )
    op.create_index(
        "idx_survey_response_audit_created",
        "survey_response_audit",
        ["survey_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "survey_decision_override",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("option_value", sa.String(length=200), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["survey_id"], ["survey.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["survey_question.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["user.id"]),
        sa.UniqueConstraint(
            "survey_id", "question_id", "option_value", name="uq_survey_decision_override"
        ),
    )


def downgrade():
    op.drop_table("survey_decision_override")
    op.drop_index("idx_survey_response_audit_created", table_name="survey_response_audit")
    op.drop_table("survey_response_audit")
    op.drop_index("idx_survey_answer_tag_value", table_name="survey_answer_tag")
    op.drop_table("survey_answer_tag")

    with op.batch_alter_table("survey_response") as batch_op:
        batch_op.drop_index("ix_survey_response_validity_status")
        batch_op.drop_column("validity_status")

    with op.batch_alter_table("survey_question") as batch_op:
        batch_op.drop_column("is_contact_info")
