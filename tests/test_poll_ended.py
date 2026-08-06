# -*- coding: utf-8 -*-
"""追加：投票截止后的管理界面与结果查看测试"""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Poll, PollOption, User, Vote


def _make_ended_poll(app, title="已截止投票", with_vote=False):
    with app.app_context():
        admin = User.query.filter_by(email="admin@example.com").one()
        poll = Poll(title=title, description="", created_by=admin.id,
                    ends_at=datetime.now(timezone.utc) - timedelta(days=1))
        db.session.add(poll)
        db.session.flush()
        db.session.add(PollOption(poll=poll, title="选项A", description="", sort_order=0))
        db.session.add(PollOption(poll=poll, title="选项B", description="", sort_order=1))
        db.session.commit()
        poll_id = poll.id
        if with_vote:
            voter = User.query.filter_by(email="verified@example.com").one()
            option = poll.options[0]
            db.session.add(Vote(poll_id=poll_id, option_id=option.id, user_id=voter.id))
            db.session.commit()
        return poll_id


def test_admin_list_shows_ended_status(client, login, app):
    login("admin@example.com")
    _make_ended_poll(app, title="已截止的食堂投票")
    html = client.get("/admin/polls").get_data(as_text=True)
    assert "已结束" in html
    assert "已截止的食堂投票" in html


def test_toggle_ended_poll_warns(client, login, app):
    login("admin@example.com")
    poll_id = _make_ended_poll(app)
    client.post(f"/admin/polls/{poll_id}/toggle")  # 先关闭
    resp = client.post(f"/admin/polls/{poll_id}/toggle", follow_redirects=True)  # 再尝试重新开放
    assert "重新开放前请先修改截止时间" in resp.text
    with app.app_context():
        assert db.session.get(Poll, poll_id).is_open is False  # 仍保持关闭


def test_admin_can_view_results_after_end(client, login, app):
    login("admin@example.com")
    poll_id = _make_ended_poll(app, with_vote=True)
    html = client.get(f"/polls/{poll_id}").get_data(as_text=True)
    assert "实时结果" in html
    assert "poll-chart" in html
    assert "已结束" in html
    assert "1 票" in html
