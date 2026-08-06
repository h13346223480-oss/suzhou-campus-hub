# -*- coding: utf-8 -*-
"""追加：柱状图与实时结果接口测试"""


def test_results_requires_login(client):
    assert client.get("/polls/1/results").status_code == 302


def test_detail_has_chart(client, login, app, tmp_path):
    login("admin@example.com")
    from test_polls import _create_poll, _poll_id
    _create_poll(client, tmp_path)
    poll_id = _poll_id(app)
    html = client.get(f"/polls/{poll_id}").get_data(as_text=True)
    assert "poll-chart" in html
    assert "实时结果" in html


def test_results_json_after_vote(client, login, app, tmp_path):
    from app.models import Poll
    login("admin@example.com")
    from test_polls import _create_poll, _poll_id
    _create_poll(client, tmp_path)
    poll_id = _poll_id(app)
    client.post("/auth/logout")

    login("verified@example.com")
    with app.app_context():
        option = Poll.query.get(poll_id).options[0]
    client.post(f"/polls/{poll_id}/vote", data={"option_id": option.id}, follow_redirects=True)
    resp = client.get(f"/polls/{poll_id}/results")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 1
    target = [o for o in data["options"] if o["id"] == option.id][0]
    assert target["count"] == 1
    assert target["percent"] == 100.0
    assert all("title" in o for o in data["options"])
