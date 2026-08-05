from conftest import photo_upload

from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import InviteCode, InviteRedemption, User, utcnow


def test_admin_can_create_and_toggle_limited_invite(client, app, login):
    login("admin@example.com")
    expires_at = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
    response = client.post("/admin/invites", data={
        "max_uses": 20,
        "expires_at": expires_at,
    }, follow_redirects=True)
    assert "邀请码已创建" in response.text
    with app.app_context():
        invite = InviteCode.query.filter(InviteCode.code != "TEST2026").one()
        assert invite.max_uses == 20
        assert invite.used_count == 0
        assert invite.usable
        invite_id = invite.id

    response = client.post(f"/admin/invites/{invite_id}/toggle", follow_redirects=True)
    assert "邀请码状态已更新" in response.text
    with app.app_context():
        assert not db.session.get(InviteCode, invite_id).is_active


def test_invite_management_requires_admin(client, login):
    login("verified@example.com")
    assert client.get("/admin/invites").status_code == 403
    assert client.post("/admin/invites", data={
        "max_uses": 20,
        "expires_at": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M"),
    }).status_code == 403


def test_admin_cannot_create_permanent_or_unlimited_invite(client, app, login):
    login("admin@example.com")
    response = client.post("/admin/invites", data={"max_uses": 0, "expires_at": ""}, follow_redirects=True)
    assert "最大使用次数必须在 1 到 1000 之间" in response.text
    with app.app_context():
        assert InviteCode.query.count() == 1


def test_bootstrap_invite_is_limited_idempotent_and_does_not_echo_code(app, monkeypatch):
    code = "SZ-RELEASE20"
    monkeypatch.setenv("INVITE_BOOTSTRAP_CODE", code)
    monkeypatch.setenv("INVITE_BOOTSTRAP_MAX_USES", "20")
    monkeypatch.setenv("INVITE_BOOTSTRAP_DAYS", "30")
    runner = app.test_cli_runner()

    first = runner.invoke(args=["bootstrap-invite"])
    second = runner.invoke(args=["bootstrap-invite"])
    assert first.exit_code == 0
    assert second.exit_code == 0
    assert code not in first.output
    assert code not in second.output
    with app.app_context():
        invite = InviteCode.query.filter_by(code=code).one()
        assert invite.max_uses == 20
        assert invite.used_count == 0
        assert invite.is_active
        expiry = invite.expires_at.replace(tzinfo=timezone.utc) if invite.expires_at.tzinfo is None else invite.expires_at
        assert expiry > utcnow() + timedelta(days=29)


def test_generated_invite_registers_one_verified_student_with_usage_record(client, app, login):
    login("admin@example.com")
    expires_at = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
    client.post("/admin/invites", data={"max_uses": 20, "expires_at": expires_at})
    client.post("/auth/logout")
    with app.app_context():
        invite = InviteCode.query.filter(InviteCode.code != "TEST2026").one()
        code = invite.code

    response = client.post("/auth/register", data={
        "nickname": "内测注册验收",
        "email": "invite-release@example.com",
        "major": "robotics_engineering",
        "enrollment_year": 2026,
        "invite_code": code,
        "student_id_photo": photo_upload(),
        "password": "StrongPass123!",
        "confirm_password": "StrongPass123!",
        "accept_terms": "y",
    }, content_type="multipart/form-data", follow_redirects=True)
    assert "注册成功" in response.text
    with app.app_context():
        user = User.query.filter_by(email="invite-release@example.com", verification_status="verified").one()
        assert user.role == "student"
        assert user.joined_via_invite is True
        invite = InviteCode.query.filter_by(code=code).one()
        assert invite.used_count == 1
        redemption = InviteRedemption.query.filter_by(user_id=user.id).one()
        assert redemption.invite_code_id == invite.id

    client.post("/auth/login", data={
        "email": "invite-release@example.com",
        "password": "StrongPass123!",
    })
    post_response = client.post("/posts/create", data={
        "title": "邀请码注册后直接发帖验收",
        "category": "校园求助",
        "content": "这是一条验证邀请码注册后立即拥有社区权限的测试内容。",
    }, follow_redirects=True)
    assert "信息已提交" in post_response.text
    assert "已收藏" in client.post("/posts/1/bookmark", follow_redirects=True).text
    assert "评论已发布" in client.post(
        "/posts/1/comment", data={"content": "邀请码用户可以直接评论。"}, follow_redirects=True
    ).text
    assert "举报已提交" in client.post(
        "/posts/1/report", data={"reason": "邀请码用户可以正常提交举报。"}, follow_redirects=True
    ).text


def test_admin_can_delete_only_unused_invite(client, app, login):
    login("admin@example.com")
    expires_at = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M")
    client.post("/admin/invites", data={"max_uses": 1, "expires_at": expires_at})
    with app.app_context():
        invite = InviteCode.query.filter(InviteCode.code != "TEST2026").one()
        invite_id = invite.id
    response = client.post(f"/admin/invites/{invite_id}/delete", follow_redirects=True)
    assert "未使用的邀请码已删除" in response.text
    with app.app_context():
        assert db.session.get(InviteCode, invite_id) is None
