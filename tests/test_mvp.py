from app.extensions import db
from app.models import InviteRedemption, Post, Report, User


def test_register_and_login(client, app):
    response = client.post("/auth/register", data={
        "email": "new@example.com", "nickname": "新同学", "major": "new_energy_science_engineering", "enrollment_year": 2026,
        "invite_code": "TEST2026", "password": "StrongPass123!", "confirm_password": "StrongPass123!", "accept_terms": "y",
    }, follow_redirects=True)
    assert "注册成功，你现在可以使用校园社区功能。" in response.text
    with app.app_context():
        user = User.query.filter_by(email="new@example.com").one()
        assert user.verification_status == "verified"
        assert user.joined_via_invite is True
        assert InviteRedemption.query.filter_by(user_id=user.id).count() == 1
        assert user.password_hash != "StrongPass123!"
    response = client.post("/auth/login", data={"email": "new@example.com", "password": "StrongPass123!"}, follow_redirects=True)
    assert "欢迎回来" in response.text


def test_unverified_user_cannot_post(client, login):
    login("pending@example.com")
    response = client.get("/posts/create", follow_redirects=True)
    assert "当前账号的校园社区权限不可用" in response.text


def test_verified_student_submits_pending_post(client, login, app):
    login("verified@example.com")
    response = client.post("/posts/create", data={"title": "演示信息：寻找课程搭子", "category": "学习搭子",
        "content": "这是满足长度要求并用于测试审核流程的演示正文。", "is_anonymous": "y"}, follow_redirects=True)
    assert "已提交" in response.text
    with app.app_context():
        post = Post.query.filter_by(title="演示信息：寻找课程搭子").one()
        assert post.status == "pending"
        assert post.is_anonymous is True


def test_admin_can_approve_post(client, login, app):
    with app.app_context():
        user = User.query.filter_by(email="verified@example.com").one()
        post = Post(author_id=user.id, title="待审核演示帖子", content="这是一个待管理员审核的演示帖子正文。", category="校园求助")
        db.session.add(post)
        db.session.commit()
        post_id = post.id
    login("admin@example.com")
    response = client.post(f"/admin/posts/{post_id}/approve", follow_redirects=True)
    assert "帖子状态已更新" in response.text
    with app.app_context():
        assert db.session.get(Post, post_id).status == "approved"


def test_normal_user_cannot_enter_admin(client, login):
    login("verified@example.com")
    response = client.get("/admin")
    assert response.status_code == 403


def test_normal_user_cannot_view_tutor_contact(client, login):
    login("verified@example.com")
    response = client.get("/admin/tutor-requests/1")
    assert response.status_code == 403
    assert "仅管理员可见-123" not in response.text


def test_admin_can_view_tutor_contact(client, login):
    login("admin@example.com")
    response = client.get("/admin/tutor-requests/1")
    assert response.status_code == 200
    assert "仅管理员可见-123" in response.text


def test_search_and_category_filter(client, login, app):
    with app.app_context():
        user = User.query.filter_by(email="verified@example.com").one()
        db.session.add(Post(author_id=user.id, title="演示信息：出售计算器", content="用于测试关键词与分类筛选的内容。", category="二手交易", status="approved"))
        db.session.commit()
    login("verified@example.com")
    response = client.get("/posts?q=计算器&category=二手交易")
    assert "出售计算器" in response.text
    response = client.get("/posts?q=计算器&category=失物招领")
    assert "出售计算器" not in response.text


def test_report_feature(client, login, app):
    login("verified@example.com")
    response = client.post("/posts/1/report", data={"reason": "演示举报：内容可能存在误导，请管理员核查。"}, follow_redirects=True)
    assert "举报已提交" in response.text
    with app.app_context():
        assert Report.query.count() == 1
        assert Report.query.first().status == "pending"


def test_html_input_is_rejected(client, login, app):
    login("verified@example.com")
    client.post("/posts/create", data={"title": "<script>alert(1)</script>", "category": "校园求助", "content": "这是一段长度足够的普通测试正文内容。"})
    with app.app_context():
        assert Post.query.filter(Post.title.contains("script")).count() == 0
