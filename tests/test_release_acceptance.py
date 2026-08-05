from io import StringIO

from flask import abort

from app.extensions import db
from app.models import Bookmark, Comment, Post, Report, User


def test_admin_verification_then_student_content_workflow(client, app, login):
    login("admin@example.com")
    with app.app_context():
        pending_id = User.query.filter_by(email="pending@example.com").one().id
    response = client.post(f"/admin/users/{pending_id}/verify", follow_redirects=True)
    assert "学生认证已通过" in response.text

    client.post("/auth/logout")
    login("pending@example.com")
    response = client.post("/posts/create", data={
        "title": "上线验收流程帖子",
        "category": "校园求助",
        "content": "这是一条用于验证发布、审核、评论、收藏和举报流程的内容。",
    }, follow_redirects=True)
    assert "信息已提交" in response.text
    with app.app_context():
        post = Post.query.filter_by(title="上线验收流程帖子").one()
        assert post.status == "pending"
        post_id = post.id

    client.post("/auth/logout")
    login("admin@example.com")
    client.post(f"/admin/posts/{post_id}/approve")
    client.post("/auth/logout")
    login("verified@example.com")

    response = client.post(f"/posts/{post_id}/comment", data={"content": "这条评论用于验收完整流程。"}, follow_redirects=True)
    assert "评论已发布" in response.text
    response = client.post(f"/posts/{post_id}/bookmark", follow_redirects=True)
    assert "已收藏" in response.text
    response = client.post(f"/posts/{post_id}/report", data={"reason": "该内容需要管理员复核具体信息。"}, follow_redirects=True)
    assert "举报已提交" in response.text

    with app.app_context():
        assert Comment.query.filter_by(post_id=post_id, status="approved").count() == 1
        assert Bookmark.query.filter_by(post_id=post_id).count() == 1
        report = Report.query.filter_by(target_type="post", target_id=post_id).one()
        report_id = report.id

    client.post("/auth/logout")
    login("admin@example.com")
    response = client.post(f"/admin/reports/{report_id}/resolve", follow_redirects=True)
    assert "举报已标记为已处理" in response.text
    with app.app_context():
        assert db.session.get(Report, report_id).status == "resolved"


def test_pending_user_cannot_bookmark_by_direct_request(client, app, login):
    login("pending@example.com")
    response = client.post("/posts/1/bookmark", follow_redirects=True)
    assert "当前账号的校园社区权限不可用" in response.text
    with app.app_context():
        assert Bookmark.query.count() == 0


def test_admin_can_revoke_restore_and_disable_normal_user(client, app, login):
    login("admin@example.com")
    with app.app_context():
        user_id = User.query.filter_by(email="verified@example.com").one().id

    response = client.post(f"/admin/users/{user_id}/revoke", follow_redirects=True)
    assert "校园社区权限已撤销" in response.text
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.verification_status == "revoked"
        assert user.role == "student"

    client.post(f"/admin/users/{user_id}/verify")
    with app.app_context():
        assert db.session.get(User, user_id).verification_status == "verified"

    client.post(f"/admin/users/{user_id}/toggle-active")
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.is_active is False
        assert user.role == "student"

    client.post("/auth/logout")
    response = login("verified@example.com")
    assert response.request.path == "/auth/login"
    assert "邮箱或密码不正确" in response.text


def test_public_pages_and_error_pages_keep_nonofficial_notice(client, app):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/_acceptance_force_403")
    def force_403():
        abort(403)

    @app.get("/_acceptance_force_413")
    def force_413():
        abort(413)

    @app.get("/_acceptance_force_500")
    def force_500():
        raise RuntimeError("acceptance error without sensitive values")

    for path in ["/", "/about", "/terms", "/privacy", "/community-rules", "/auth/login", "/auth/register", "/auth/forgot-password"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "学生自发 · 非官方" in response.text
        assert "与学校官方无隶属或授权关系" in response.text

    not_found = client.get("/this-page-does-not-exist")
    assert not_found.status_code == 404
    assert "没有找到这个页面" in not_found.text
    assert "与学校官方无隶属或授权关系" in not_found.text

    forbidden = client.get("/_acceptance_force_403")
    assert forbidden.status_code == 403
    assert "这里需要更高权限" in forbidden.text
    assert "与学校官方无隶属或授权关系" in forbidden.text

    too_large = client.get("/_acceptance_force_413")
    assert too_large.status_code == 413
    assert "上传文件过大" in too_large.text
    assert "与学校官方无隶属或授权关系" in too_large.text

    server_error = client.get("/_acceptance_force_500")
    assert server_error.status_code == 500
    assert "页面暂时无法打开" in server_error.text
    assert "与学校官方无隶属或授权关系" in server_error.text


def test_request_logs_exclude_credentials_and_query_values(client, app):
    stream = StringIO()
    original_stream = app.logger.handlers[0].stream
    app.logger.handlers[0].stream = stream
    try:
        client.post("/auth/login?email=leak@example.com", data={
            "email": "private@example.com",
            "password": "DoNotLogThisPassword!",
        })
    finally:
        app.logger.handlers[0].stream = original_stream
    logs = stream.getvalue()
    assert "method=POST path=/auth/login status=200" in logs
    assert "private@example.com" not in logs
    assert "leak@example.com" not in logs
    assert "DoNotLogThisPassword!" not in logs


def test_guest_comment_section_shows_login_button(client):
    response = client.get("/posts/1")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "请先" in text
    assert ">登录</a>" in text
    assert "后发表评论" in text
    assert "/auth/login" in text


def test_verified_user_sees_comment_form(client, login):
    login("verified@example.com")
    response = client.get("/posts/1")
    assert response.status_code == 200
    assert "发表评论" in response.get_data(as_text=True)

def test_modern_interaction_assets_are_served(client):
    html = client.get("/").get_data(as_text=True)
    assert "js/app.js" in html
    js = client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "to-top" in js.get_data(as_text=True)
    css = client.get("/static/css/site.css")
    assert "to-top" in css.get_data(as_text=True)
    assert "prefers-reduced-motion" in css.get_data(as_text=True)
