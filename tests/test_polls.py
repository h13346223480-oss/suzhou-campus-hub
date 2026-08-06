# -*- coding: utf-8 -*-
"""投票功能测试"""
from io import BytesIO

from PIL import Image

from app.extensions import db
from app.models import Poll, PollOption, User, Vote


def _make_image(name="option.png"):
    buf = BytesIO()
    Image.new("RGB", (8, 8), "teal").save(buf, format="PNG")
    buf.seek(0)
    return (buf, name)


def _create_poll(client, tmp_path, title="校园食堂满意度", with_image=True):
    app = client.application
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    data = {
        "title": title,
        "description": "请选出你最喜欢的食堂窗口。",
        "ends_at": "",
        "option_title_new_0": "一楼大众餐",
        "option_desc_new_0": "性价比高",
        "option_title_new_1": "二楼特色餐",
        "option_desc_new_1": "选择丰富",
    }
    if with_image:
        data["option_image_new_0"] = _make_image()
    return client.post("/admin/polls/create", data=data, content_type="multipart/form-data", follow_redirects=True)


def _poll_id(app, title="校园食堂满意度"):
    with app.app_context():
        return Poll.query.filter_by(title=title).first().id


def test_polls_list_requires_login(client):
    assert client.get("/polls").status_code == 302


def test_poll_detail_requires_login(client, app, tmp_path):
    login_data = {"email": "admin@example.com", "password": "Password123!"}
    client.post("/auth/login", data=login_data)
    _create_poll(client, tmp_path)
    poll_id = _poll_id(app)
    client.post("/auth/logout")
    assert client.get(f"/polls/{poll_id}").status_code == 302


def test_admin_can_create_poll(client, login, app, tmp_path):
    login("admin@example.com")
    resp = _create_poll(client, tmp_path)
    assert "投票已创建" in resp.text
    with app.app_context():
        poll = Poll.query.filter_by(title="校园食堂满意度").one()
        assert len(poll.options) == 2
        assert poll.options[0].title == "一楼大众餐"
        assert poll.options[0].image_path is not None
    # 出现在公开列表（登录用户可见）
    assert client.get("/polls").status_code == 200


def test_admin_page_admin_only(client, login):
    login("verified@example.com")
    assert client.get("/admin/polls").status_code == 403


def test_user_can_vote_once(client, login, app, tmp_path):
    login("admin@example.com")
    _create_poll(client, tmp_path)
    poll_id = _poll_id(app)
    client.post("/auth/logout")

    login("verified@example.com")
    with app.app_context():
        option_id = db.session.get(Poll, poll_id).options[0].id
    resp = client.post(f"/polls/{poll_id}/vote", data={"option_id": option_id}, follow_redirects=True)
    assert "投票成功" in resp.text
    # 重复投票被拒绝
    resp2 = client.post(f"/polls/{poll_id}/vote", data={"option_id": option_id}, follow_redirects=True)
    assert "不能重复投票" in resp2.text
    # 详情页显示结果
    detail = client.get(f"/polls/{poll_id}").get_data(as_text=True)
    assert "1 票" in detail


def test_vote_invalid_option_rejected(client, login, app, tmp_path):
    login("admin@example.com")
    _create_poll(client, tmp_path)
    poll_id = _poll_id(app)
    client.post("/auth/logout")
    login("verified@example.com")
    resp = client.post(f"/polls/{poll_id}/vote", data={"option_id": 99999}, follow_redirects=True)
    assert "有效的选项" in resp.text


def test_closed_poll_rejected(client, login, app, tmp_path):
    login("admin@example.com")
    _create_poll(client, tmp_path)
    poll_id = _poll_id(app)
    client.post(f"/admin/polls/{poll_id}/toggle", follow_redirects=True)  # 关闭
    client.post("/auth/logout")
    login("verified@example.com")
    with app.app_context():
        option_id = db.session.get(Poll, poll_id).options[0].id
    resp = client.post(f"/polls/{poll_id}/vote", data={"option_id": option_id}, follow_redirects=True)
    assert "已结束或未开放" in resp.text


def test_admin_can_edit_poll(client, login, app, tmp_path):
    login("admin@example.com")
    _create_poll(client, tmp_path)
    poll_id = _poll_id(app)
    with app.app_context():
        option_id = db.session.get(Poll, poll_id).options[0].id
    data = {
        "title": "校园食堂满意度（更新）",
        "description": "更新后的说明。",
        "ends_at": "",
        f"option_title_{option_id}": "一楼大众餐（改）",
        f"option_desc_{option_id}": "",
        "option_title_new_0": "三楼夜宵档",
        "option_desc_new_0": "",
    }
    resp = client.post(f"/admin/polls/{poll_id}/edit", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert "投票已更新" in resp.text
    with app.app_context():
        poll = db.session.get(Poll, poll_id)
        assert poll.title == "校园食堂满意度（更新）"
        assert poll.options[0].title == "一楼大众餐（改）"
        assert len(poll.options) == 3


def test_delete_option_with_votes_rejected(client, login, app, tmp_path):
    login("admin@example.com")
    _create_poll(client, tmp_path)
    poll_id = _poll_id(app)
    client.post("/auth/logout")
    login("verified@example.com")
    with app.app_context():
        option_id = db.session.get(Poll, poll_id).options[0].id
    client.post(f"/polls/{poll_id}/vote", data={"option_id": option_id}, follow_redirects=True)
    client.post("/auth/logout")

    login("admin@example.com")
    resp = client.post(
        f"/admin/polls/{poll_id}/edit",
        data={"title": "校园食堂满意度", "description": "", "ends_at": "",
              f"delete_option_{option_id}": "y"},
        follow_redirects=True)
    assert "已有投票的选项不能删除" in resp.text


def test_admin_can_delete_poll(client, login, app, tmp_path):
    login("admin@example.com")
    _create_poll(client, tmp_path)
    poll_id = _poll_id(app)
    resp = client.post(f"/admin/polls/{poll_id}/delete", follow_redirects=True)
    assert "投票已删除" in resp.text
    with app.app_context():
        assert db.session.get(Poll, poll_id) is None
