"""个人资料：昵称修改、头像上传/移除、头像引导弹窗与作者小头像显示测试。"""
from io import BytesIO

from PIL import Image

from app.extensions import db
from app.models import User


def _png_bytes():
    buf = BytesIO()
    Image.new("RGB", (16, 16), "navy").save(buf, format="PNG")
    buf.seek(0)
    return buf


# ---------- 昵称修改 ----------

def test_update_nickname(client, login, app):
    login("verified@example.com")
    response = client.post("/profile", data={"nickname": "新昵称"}, follow_redirects=True)
    assert response.status_code == 200
    assert "昵称已更新" in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(email="verified@example.com").one().nickname == "新昵称"


def test_update_nickname_rejects_short_and_html(client, login, app):
    login("verified@example.com")
    response = client.post("/profile", data={"nickname": "a"}, follow_redirects=True)
    assert "昵称已更新" not in response.get_data(as_text=True)
    response = client.post("/profile", data={"nickname": "<script>alert(1)</script>"}, follow_redirects=True)
    assert "昵称已更新" not in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(email="verified@example.com").one().nickname == "认证学生"


def test_profile_requires_login(client):
    assert client.get("/profile").status_code == 302


# ---------- 头像上传 / 移除 ----------

def test_upload_avatar(client, login, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = tmp_path
    login("verified@example.com")
    response = client.post(
        "/profile/avatar",
        data={"avatar": (_png_bytes(), "avatar.png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "头像已更新" in response.get_data(as_text=True)
    with app.app_context():
        user = User.query.filter_by(email="verified@example.com").one()
        assert user.avatar and user.avatar.startswith("uploads/")
        assert (tmp_path / user.avatar.split("/")[-1]).is_file()


def test_upload_avatar_rejects_bad_type(client, login, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = tmp_path
    login("verified@example.com")
    response = client.post(
        "/profile/avatar",
        data={"avatar": (BytesIO(b"<svg onload=alert(1)></svg>"), "bad.svg")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "头像已更新" not in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(email="verified@example.com").one().avatar is None


def test_upload_avatar_rejects_fake_image(client, login, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = tmp_path
    login("verified@example.com")
    response = client.post(
        "/profile/avatar",
        data={"avatar": (BytesIO(b"not-a-real-image"), "fake.png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "头像已更新" not in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(email="verified@example.com").one().avatar is None


def test_remove_avatar(client, login, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = tmp_path
    login("verified@example.com")
    with app.app_context():
        user = User.query.filter_by(email="verified@example.com").one()
        user.avatar = "uploads/old.png"
        db.session.commit()
    response = client.post("/profile/avatar-remove", follow_redirects=True)
    assert response.status_code == 200
    assert "已移除头像" in response.get_data(as_text=True)
    with app.app_context():
        assert User.query.filter_by(email="verified@example.com").one().avatar is None


# ---------- 注册完成后的头像引导弹窗 ----------

def _register_and_login(client, email="fresh@example.com"):
    client.post("/auth/register", data={
        "register_type": "invite",
        "email": email,
        "nickname": "新同学",
        "major": "robotics_engineering",
        "enrollment_year": 2026,
        "invite_code": "TEST2026",
        "password": "StrongPass123!",
        "confirm_password": "StrongPass123!",
        "accept_terms": "y",
    }, content_type="multipart/form-data", follow_redirects=True)
    client.post("/auth/login", data={"email": email, "password": "StrongPass123!"}, follow_redirects=True)


def test_avatar_guide_modal_shows_after_registration(client):
    _register_and_login(client)
    text = client.get("/").get_data(as_text=True)
    assert "avatarGuideModal" in text
    assert "设置你的头像" in text


def test_avatar_guide_modal_hidden_for_existing_user(client, login):
    login("verified@example.com")
    text = client.get("/").get_data(as_text=True)
    assert "avatarGuideModal" not in text


def test_avatar_guide_modal_hidden_after_dismiss(client):
    _register_and_login(client)
    response = client.post("/profile/avatar-dismiss")
    assert response.status_code == 204
    text = client.get("/").get_data(as_text=True)
    assert "avatarGuideModal" not in text


def test_avatar_guide_modal_hidden_after_uploading_avatar(client, app, tmp_path):
    app.config["UPLOAD_FOLDER"] = tmp_path
    _register_and_login(client)
    with app.app_context():
        user = User.query.filter_by(email="fresh@example.com").one()
        user.avatar = "uploads/x.png"
        db.session.commit()
    text = client.get("/").get_data(as_text=True)
    assert "avatarGuideModal" not in text


def test_avatar_guide_modal_hidden_for_guest(client):
    text = client.get("/").get_data(as_text=True)
    assert "avatarGuideModal" not in text


# ---------- 作者名称处显示小头像 ----------

def test_author_avatar_in_post_list(client):
    text = client.get("/posts").get_data(as_text=True)
    assert "author-line" in text
    # 未设置头像时显示首字母占位圆
    assert "mini-avatar fallback" in text


def test_author_avatar_in_post_detail_and_comments(client):
    text = client.get("/posts/1").get_data(as_text=True)
    assert "author-line" in text
    assert "mini-avatar" in text
