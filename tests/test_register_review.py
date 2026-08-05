from conftest import photo_upload

from app.extensions import db
from app.models import InviteRedemption, User


def _register(client, email, photo=True, invite="", password="StrongPass123!"):
    data = {
        "email": email,
        "nickname": "注册审核同学",
        "major": "robotics_engineering",
        "enrollment_year": 2026,
        "password": password,
        "confirm_password": password,
        "accept_terms": "y",
    }
    if photo:
        data["student_id_photo"] = photo_upload()
    if invite:
        data["invite_code"] = invite
    return client.post("/auth/register", data=data, content_type="multipart/form-data", follow_redirects=True)


def test_register_page_hints_invite_skips_review(client):
    text = client.get("/auth/register").get_data(as_text=True)
    assert "填写有效邀请码可立即认证通过" in text


def test_register_without_invite_creates_pending_user_with_photo(client, app, tmp_path):
    app.config["ID_PHOTO_FOLDER"] = tmp_path
    response = _register(client, "review-pending@example.com")
    assert "请等待管理员审核" in response.get_data(as_text=True)
    with app.app_context():
        user = User.query.filter_by(email="review-pending@example.com").one()
        assert user.verification_status == "pending"
        assert user.joined_via_invite is False
        assert user.student_id_photo
        assert (tmp_path / user.student_id_photo).is_file()


def test_register_requires_photo(client, app):
    response = _register(client, "no-photo@example.com", photo=False)
    assert "请上传校园卡人像面照片" in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(email="no-photo@example.com").first() is None


def test_register_rejects_invalid_invite_code(client, app):
    response = _register(client, "bad-invite@example.com", invite="WRONG-CODE")
    assert "邀请码无效" in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(email="bad-invite@example.com").first() is None


def test_valid_invite_registration_is_verified_without_review(client, app):
    response = _register(client, "invite-ok@example.com", invite="TEST2026")
    assert "你现在可以使用校园社区功能" in response.get_data(as_text=True)
    with app.app_context():
        user = User.query.filter_by(email="invite-ok@example.com").one()
        assert user.verification_status == "verified"
        assert user.joined_via_invite is True
        assert InviteRedemption.query.filter_by(user_id=user.id).count() == 1


def test_student_id_photo_only_visible_to_admin(client, app, login, tmp_path):
    app.config["ID_PHOTO_FOLDER"] = tmp_path
    _register(client, "photo-view@example.com")
    with app.app_context():
        user_id = User.query.filter_by(email="photo-view@example.com").one().id
    assert client.get(f"/admin/users/{user_id}/id-photo").status_code == 302
    login("verified@example.com")
    assert client.get(f"/admin/users/{user_id}/id-photo").status_code == 403
    client.post("/auth/logout")
    login("admin@example.com")
    assert client.get(f"/admin/users/{user_id}/id-photo").status_code == 200


def test_admin_verify_grants_community_permission(client, app, login):
    _register(client, "approve-me@example.com")
    with app.app_context():
        user_id = User.query.filter_by(email="approve-me@example.com").one().id
    login("admin@example.com")
    response = client.post(f"/admin/users/{user_id}/verify", follow_redirects=True)
    assert "学生认证已通过" in response.text
    client.post("/auth/logout")
    login("approve-me@example.com", "StrongPass123!")
    response = client.get("/posts/create", follow_redirects=True)
    assert response.status_code == 200
    assert "发布一条校园信息" in response.get_data(as_text=True)


def test_register_rejects_fake_photo(client, app):
    from io import BytesIO
    data = {
        "email": "fake-photo@example.com",
        "nickname": "伪造照片同学",
        "major": "robotics_engineering",
        "enrollment_year": 2026,
        "student_id_photo": (BytesIO(b"not-a-real-image"), "fake.png"),
        "password": "StrongPass123!",
        "confirm_password": "StrongPass123!",
        "accept_terms": "y",
    }
    response = client.post("/auth/register", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert "图片内容无效" in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(email="fake-photo@example.com").first() is None
