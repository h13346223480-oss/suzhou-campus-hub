"""normalize user and resource major codes

Revision ID: b5c8d9e0f121
Revises: a4b7c8d9e010
Create Date: 2026-08-02 16:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "b5c8d9e0f121"
down_revision = "a4b7c8d9e010"
branch_labels = None
depends_on = None

ROBOTICS = "robotics_engineering"
INTELLIGENT_MANUFACTURING = "intelligent_manufacturing_engineering"
NEW_ENERGY = "new_energy_science_engineering"
OTHER = "other"
PENDING = "pending_confirmation"
GENERAL = "general"


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("major_code", sa.String(length=50), nullable=False,
                                      server_default=PENDING))
        batch_op.create_index("ix_user_major_code", ["major_code"], unique=False)
        batch_op.create_check_constraint(
            "ck_user_major_code",
            "major_code IN ('robotics_engineering', 'intelligent_manufacturing_engineering', "
            "'new_energy_science_engineering', 'other', 'pending_confirmation')",
        )

    user = sa.table(
        "user",
        sa.column("role", sa.String()),
        sa.column("major", sa.String()),
        sa.column("major_code", sa.String()),
    )
    legacy_combined = "机器人" + "/" + "智能制造"
    user_mappings = [
        (["机器人工程"], ROBOTICS, "机器人工程"),
        (["智能制造工程"], INTELLIGENT_MANUFACTURING, "智能制造工程"),
        (["新能源", "新能源科学与工程"], NEW_ENERGY, "新能源科学与工程"),
        (["其他"], OTHER, "其他"),
        ([legacy_combined, "专业待确认", "待确认"], PENDING, "待确认"),
    ]
    for legacy_values, code, label in user_mappings:
        op.execute(user.update().where(user.c.major.in_(legacy_values)).values(
            major_code=code, major=label
        ))
    op.execute(user.update().where(user.c.role == "admin").values(major_code=OTHER))

    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("major_code", existing_type=sa.String(length=50),
                              server_default=None)

    with op.batch_alter_table("english_resource") as batch_op:
        batch_op.add_column(sa.Column("major_code", sa.String(length=50), nullable=False,
                                      server_default=GENERAL))
        batch_op.create_index("ix_english_resource_major_code", ["major_code"], unique=False)
        batch_op.create_check_constraint(
            "ck_english_resource_major_code",
            "major_code IN ('general', 'robotics_engineering', "
            "'intelligent_manufacturing_engineering', 'new_energy_science_engineering', 'other')",
        )

    resource = sa.table(
        "english_resource",
        sa.column("major", sa.String()),
        sa.column("major_code", sa.String()),
    )
    resource_mappings = [
        (["通用", legacy_combined], GENERAL, "通用"),
        (["机器人工程"], ROBOTICS, "机器人工程"),
        (["智能制造工程"], INTELLIGENT_MANUFACTURING, "智能制造工程"),
        (["新能源", "新能源科学与工程"], NEW_ENERGY, "新能源科学与工程"),
        (["其他"], OTHER, "其他"),
    ]
    for legacy_values, code, label in resource_mappings:
        op.execute(resource.update().where(resource.c.major.in_(legacy_values)).values(
            major_code=code, major=label
        ))

    with op.batch_alter_table("english_resource") as batch_op:
        batch_op.alter_column("major_code", existing_type=sa.String(length=50),
                              server_default=None)

    replace_freshman_major_options()


def replace_freshman_major_options():
    bind = op.get_bind()
    survey = sa.table("survey", sa.column("id", sa.Integer()), sa.column("slug", sa.String()))
    question = sa.table(
        "survey_question",
        sa.column("id", sa.Integer()),
        sa.column("survey_id", sa.Integer()),
        sa.column("title", sa.String()),
    )
    option = sa.table(
        "survey_option",
        sa.column("question_id", sa.Integer()),
        sa.column("label", sa.String()),
        sa.column("value", sa.String()),
        sa.column("sort_order", sa.Integer()),
    )
    survey_id = bind.execute(sa.select(survey.c.id).where(survey.c.slug == "freshman-needs")).scalar()
    if survey_id is None:
        return
    question_id = bind.execute(sa.select(question.c.id).where(
        question.c.survey_id == survey_id,
        question.c.title == "你的专业方向是什么？",
    )).scalar()
    if question_id is None:
        return
    bind.execute(option.delete().where(option.c.question_id == question_id))
    op.bulk_insert(option, [
        {"question_id": question_id, "label": "机器人工程", "value": ROBOTICS, "sort_order": 1},
        {"question_id": question_id, "label": "智能制造工程", "value": INTELLIGENT_MANUFACTURING,
         "sort_order": 2},
        {"question_id": question_id, "label": "新能源科学与工程", "value": NEW_ENERGY,
         "sort_order": 3},
        {"question_id": question_id, "label": "其他", "value": OTHER, "sort_order": 4},
    ])


def downgrade():
    with op.batch_alter_table("english_resource") as batch_op:
        batch_op.drop_constraint("ck_english_resource_major_code", type_="check")
        batch_op.drop_index("ix_english_resource_major_code")
        batch_op.drop_column("major_code")
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_constraint("ck_user_major_code", type_="check")
        batch_op.drop_index("ix_user_major_code")
        batch_op.drop_column("major_code")
