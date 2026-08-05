import pytest

from app import create_app
from app.extensions import db
from app.majors import NEW_ENERGY_SCIENCE_ENGINEERING, OTHER, ROBOTICS_ENGINEERING
from app.models import InviteCode, Post, TutorRequest, User
from config import TestConfig


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        admin = make_user("管理员", "admin@example.com", OTHER, "admin", "verified")
        verified = make_user("认证学生", "verified@example.com", ROBOTICS_ENGINEERING, "student", "verified")
        pending = make_user("待认证学生", "pending@example.com", NEW_ENERGY_SCIENCE_ENGINEERING, "student", "pending")
        db.session.add_all([admin, verified, pending, InviteCode(code="TEST2026", max_uses=20)])
        db.session.flush()
        post = Post(author_id=verified.id, title="演示信息：学习搭子", content="这是用于自动化测试的中文演示内容。", category="学习搭子", status="approved")
        tutor_request = TutorRequest(contact_name="测试家长", contact_method="仅管理员可见-123", student_grade="初一", subjects="数学", current_level="基础", target="巩固", location="线上", budget="100元", notes="测试")
        db.session.add_all([post, tutor_request])
        db.session.commit()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(nickname, email, major_code, role, status):
    user = User(nickname=nickname, email=email, enrollment_year=2026, role=role, verification_status=status)
    user.set_major(major_code)
    user.set_password("Password123!")
    return user


@pytest.fixture()
def login(client):
    def _login(email, password="Password123!"):
        return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)
    return _login
