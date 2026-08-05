from app.extensions import db
from app.models import SiteStat, User


def test_footer_shows_visit_count_and_increments_once_per_visitor(client, app):
    first = client.get("/")
    assert "累计访问 1 人" in first.get_data(as_text=True)
    second = client.get("/")
    assert "累计访问 1 人" in second.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(SiteStat, 1).total_visits == 1


def test_new_visitor_session_increments_counter(app):
    c1 = app.test_client()
    c1.get("/")
    with app.app_context():
        assert db.session.get(SiteStat, 1).total_visits == 1
    c2 = app.test_client()
    c2.get("/")
    with app.app_context():
        assert db.session.get(SiteStat, 1).total_visits == 2


def test_admin_stats_page_shows_basic_counts(client, app, login):
    login("admin@example.com")
    response = client.get("/admin/stats")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "累计访问人数" in text
    assert "注册用户总数" in text
    assert "已认证用户" in text
    assert "待审核用户" in text
    assert "帖子总数" in text
    assert "评论总数" in text
    assert "新生指南总数" in text


def test_non_admin_cannot_access_stats(client, login):
    login("verified@example.com")
    assert client.get("/admin/stats").status_code == 403


def test_admin_resets_user_password(client, app, login):
    login("admin@example.com")
    with app.app_context():
        uid = User.query.filter_by(email="verified@example.com").one().id
    page = client.get(f"/admin/users/{uid}/reset-password")
    assert page.status_code == 200
    assert "重置" in page.get_data(as_text=True)
    client.post(f"/admin/users/{uid}/reset-password", data={
        "new_password": "NewPass123!",
        "confirm_password": "NewPass123!",
    })
    client.post("/auth/logout")
    login("verified@example.com", "NewPass123!")
    assert client.get("/posts/create").status_code == 200
    client.post("/auth/logout")
    response = client.post("/auth/login", data={"email": "verified@example.com", "password": "Password123!"})
    assert "邮箱或密码不正确" in response.get_data(as_text=True)


def test_admin_cannot_reset_own_password(client, app, login):
    login("admin@example.com")
    with app.app_context():
        uid = User.query.filter_by(email="admin@example.com").one().id
    response = client.get(f"/admin/users/{uid}/reset-password")
    assert response.status_code == 302
