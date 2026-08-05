from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from conftest import photo_upload

from app.extensions import db
from app.majors import (
    INTELLIGENT_MANUFACTURING_ENGINEERING,
    NEW_ENERGY_SCIENCE_ENGINEERING,
    OTHER,
    PENDING_CONFIRMATION,
    ROBOTICS_ENGINEERING,
)
from app.models import EnglishResource, Post, Survey, SurveyResponse, User
from app.routes.survey_admin import analyze_responses
from app.seed import ensure_demo_survey


def add_user(email, nickname, major_code, status="verified"):
    user = User(
        email=email,
        nickname=nickname,
        enrollment_year=2026,
        role="student",
        verification_status=status,
    )
    user.set_major(major_code)
    user.set_password("Password123!")
    db.session.add(user)
    db.session.flush()
    return user


def test_register_page_has_four_distinct_controlled_major_choices(client):
    response = client.get("/auth/register")
    assert response.status_code == 200
    for code, label in [
        (ROBOTICS_ENGINEERING, "机器人工程"),
        (INTELLIGENT_MANUFACTURING_ENGINEERING, "智能制造工程"),
        (NEW_ENERGY_SCIENCE_ENGINEERING, "新能源科学与工程"),
        (OTHER, "其他"),
    ]:
        assert f'value="{code}"' in response.text
        assert label in response.text
    legacy_combined = "机器人" + "/" + "智能制造"
    assert legacy_combined not in response.text


def test_registration_persists_authoritative_major_code(client, app):
    response = client.post("/auth/register", data={
        "email": "major-code@example.com",
        "nickname": "专业代码同学",
        "major": INTELLIGENT_MANUFACTURING_ENGINEERING,
        "enrollment_year": 2026,
        "invite_code": "TEST2026",
        "student_id_photo": photo_upload(),
        "password": "Password123!",
        "confirm_password": "Password123!",
        "accept_terms": "y",
    }, content_type="multipart/form-data", follow_redirects=True)
    assert "注册成功" in response.text
    with app.app_context():
        user = User.query.filter_by(email="major-code@example.com").one()
        assert user.major_code == INTELLIGENT_MANUFACTURING_ENGINEERING
        assert user.major == "智能制造工程"


def test_database_rejects_uncontrolled_user_major_code(app):
    with app.app_context():
        user = User(
            email="free-text-major@example.com",
            nickname="自由文本专业测试",
            major="随意填写的专业",
            major_code="free_text_major",
            enrollment_year=2026,
        )
        user.set_password("Password123!")
        db.session.add(user)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_legacy_pending_user_is_prompted_and_must_choose_between_two_majors(client, app):
    with app.app_context():
        user = add_user("legacy-major@example.com", "旧专业同学", PENDING_CONFIRMATION)
        user.verification_status = "verified"
        db.session.commit()

    response = client.post("/auth/login", data={
        "email": "legacy-major@example.com",
        "password": "Password123!",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    profile = client.get(response.headers["Location"])
    assert "请重新确认专业" in profile.text
    assert "不会自动猜测" in profile.text

    edit_page = client.get("/profile/major")
    assert "机器人工程" in edit_page.text
    assert "智能制造工程" in edit_page.text
    assert "新能源科学与工程" not in edit_page.text
    rejected = client.post("/profile/major", data={"major": OTHER}, follow_redirects=True)
    assert "专业信息已更新" not in rejected.text
    with app.app_context():
        assert User.query.filter_by(email="legacy-major@example.com").one().major_code == PENDING_CONFIRMATION

    confirmed = client.post("/profile/major", data={
        "major": INTELLIGENT_MANUFACTURING_ENGINEERING,
    }, follow_redirects=True)
    assert "专业信息已更新" in confirmed.text
    assert "智能制造工程" in confirmed.text
    with app.app_context():
        user = User.query.filter_by(email="legacy-major@example.com").one()
        assert user.major_code == INTELLIGENT_MANUFACTURING_ENGINEERING
        assert user.requires_major_confirmation is False


def test_admin_user_list_displays_and_filters_pending_confirmation(client, login, app):
    with app.app_context():
        add_user("pending-major@example.com", "专业待确认同学", PENDING_CONFIRMATION)
        db.session.commit()
    login("admin@example.com")
    response = client.get(f"/admin/users?major={PENDING_CONFIRMATION}")
    assert response.status_code == 200
    assert "专业待确认同学" in response.text
    assert "待确认" in response.text
    assert "认证学生" not in response.text


def test_pending_major_is_not_counted_as_a_concrete_major(app):
    with app.app_context():
        admin = User.query.filter_by(role="admin").one()
        pending_user = add_user("pending-stats@example.com", "统计待确认同学", PENDING_CONFIRMATION)
        survey = Survey(
            title="专业统计测试",
            slug="major-stats-test",
            description="验证待确认专业不会被误计入具体专业。",
            status="published",
            use_account_profile_data=True,
            created_by=admin.id,
        )
        db.session.add(survey)
        db.session.flush()
        response = SurveyResponse(survey_id=survey.id, user_id=pending_user.id, validity_status="valid")
        db.session.add(response)
        db.session.flush()

        analysis = analyze_responses(survey, [response])

        assert analysis["majors"] == {"待确认": 1}
        assert "机器人工程" not in analysis["majors"]
        assert "智能制造工程" not in analysis["majors"]


def test_posts_and_learning_resources_filter_by_major_code(client, login, app):
    with app.app_context():
        intelligent_user = add_user(
            "intelligent@example.com", "智造同学", INTELLIGENT_MANUFACTURING_ENGINEERING
        )
        db.session.add(Post(
            author_id=intelligent_user.id,
            title="智能制造工程学习交流",
            content="分享智能制造工程课程学习和项目协作经验。",
            category="学习搭子",
            status="approved",
        ))
        robotics_resource = EnglishResource(
            title="机器人工程术语", category="专业词汇", content="用于机器人工程课堂的测试资料内容。",
            difficulty="入门", status="published",
        )
        robotics_resource.set_major(ROBOTICS_ENGINEERING)
        intelligent_resource = EnglishResource(
            title="智能制造工程术语", category="专业词汇", content="用于智能制造工程课堂的测试资料内容。",
            difficulty="入门", status="published",
        )
        intelligent_resource.set_major(INTELLIGENT_MANUFACTURING_ENGINEERING)
        db.session.add_all([robotics_resource, intelligent_resource])
        db.session.commit()

    login("verified@example.com")
    posts = client.get(f"/posts?major={INTELLIGENT_MANUFACTURING_ENGINEERING}")
    assert "智能制造工程学习交流" in posts.text
    assert "演示信息：学习搭子" not in posts.text
    resources = client.get(f"/english-hub?major={ROBOTICS_ENGINEERING}")
    assert "机器人工程术语" in resources.text
    assert "智能制造工程术语" not in resources.text


def test_seed_survey_uses_exact_four_major_options(app):
    with app.app_context():
        admin = User.query.filter_by(role="admin").one()
        ensure_demo_survey(admin)
        db.session.commit()
        survey = Survey.query.filter_by(slug="freshman-needs").one()
        question = next(item for item in survey.questions if item.title == "你的专业方向是什么？")
        assert [(option.value, option.label) for option in question.options] == [
            (ROBOTICS_ENGINEERING, "机器人工程"),
            (INTELLIGENT_MANUFACTURING_ENGINEERING, "智能制造工程"),
            (NEW_ENERGY_SCIENCE_ENGINEERING, "新能源科学与工程"),
            (OTHER, "其他"),
        ]


def test_legacy_combined_option_is_absent_from_active_project_files():
    project_root = Path(__file__).resolve().parents[1]
    legacy_combined = "机器人" + "/" + "智能制造"
    for root_name in ["app", "tests", "README.md"]:
        root = project_root / root_name
        files = [root] if root.is_file() else list(root.rglob("*"))
        for path in files:
            if path.is_file() and path.suffix in {".py", ".html", ".md"}:
                assert legacy_combined not in path.read_text(encoding="utf-8"), path
