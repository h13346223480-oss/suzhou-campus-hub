from app.models import User


def test_admin_can_create_regular_user(client, app, login):
    login("admin@example.com")
    response = client.post("/admin/users/new", data={
        "email": "newstudent@example.com", "nickname": "新同学",
        "role": "student", "password": "NewUser123!",
    })
    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(email="newstudent@example.com").first()
        assert user is not None
        assert not user.is_admin
        assert user.is_verified and user.is_active


def test_admin_can_create_admin_user(client, app, login):
    login("admin@example.com")
    client.post("/admin/users/new", data={
        "email": "newadmin@example.com", "nickname": "新管理员",
        "role": "admin", "password": "AdminNew123!",
    })
    with app.app_context():
        user = User.query.filter_by(email="newadmin@example.com").first()
        assert user is not None
        assert user.is_admin
        assert user.is_verified and user.is_active


def test_created_user_can_login(client, app, login):
    login("admin@example.com")
    client.post("/admin/users/new", data={
        "email": "fresh@example.com", "nickname": "新生",
        "role": "student", "password": "FreshPass123!",
    })
    client.post("/auth/logout")
    response = client.post("/auth/login", data={"email": "fresh@example.com", "password": "FreshPass123!"})
    assert response.status_code == 302


def test_duplicate_email_is_rejected(client, app, login):
    login("admin@example.com")
    response = client.post("/admin/users/new", data={
        "email": "verified@example.com", "nickname": "重复邮箱",
        "role": "student", "password": "DupUser123!",
    })
    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="verified@example.com").count() == 1


def test_non_admin_cannot_create_user(client, login):
    login("verified@example.com")
    assert client.get("/admin/users/new").status_code == 403
    assert client.post("/admin/users/new", data={
        "email": "hacker@example.com", "nickname": "越权者",
        "role": "admin", "password": "HackUser123!",
    }).status_code == 403
