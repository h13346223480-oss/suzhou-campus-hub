"""AI 助手：登录鉴权、接口校验、用量记录与管理员统计测试。"""
import pytest

from app.extensions import db
from app.models import AiChatUsage, User


@pytest.fixture()
def ai_client(client, login):
    """登录认证学生并配置模拟的 DeepSeek API Key。"""
    client.application.config["DEEPSEEK_API_KEY"] = "test-key"
    login("verified@example.com")
    return client


def _chat_payload(client, message):
    return client.post("/api/ai/chat", json={"message": message})


def test_ai_chat_requires_login(client):
    client.application.config["DEEPSEEK_API_KEY"] = "test-key"
    response = _chat_payload(client, "你好")
    assert response.status_code == 401


def test_ai_chat_disabled_without_api_key(client, login):
    # 显式清空 Key，避免依赖真实 .env 中的 DEEPSEEK_API_KEY
    client.application.config["DEEPSEEK_API_KEY"] = ""
    login("verified@example.com")
    response = _chat_payload(client, "你好")
    assert response.status_code == 503


def test_ai_chat_rejects_empty_and_long_messages(ai_client):
    assert _chat_payload(ai_client, "").status_code == 400
    assert _chat_payload(ai_client, "   ").status_code == 400
    long_message = "测" * 501
    assert _chat_payload(ai_client, long_message).status_code == 400


def test_ai_chat_success_records_usage(ai_client, monkeypatch, app):
    fake_usage = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "prompt_cache_hit_tokens": 0,
    }
    monkeypatch.setattr(
        "app.routes.ai.chat_once",
        lambda messages: ("你好，很高兴为你服务。", fake_usage),
    )
    response = _chat_payload(ai_client, "你好")
    assert response.status_code == 200
    assert response.get_json()["reply"] == "你好，很高兴为你服务。"

    with app.app_context():
        user = User.query.filter_by(email="verified@example.com").one()
        record = AiChatUsage.query.filter_by(user_id=user.id).one()
        assert record.prompt_tokens == 100
        assert record.completion_tokens == 50
        assert record.total_tokens == 150
        assert record.model == "deepseek-v4-flash"
        # 输入 1 元/百万 + 输出 2 元/百万：(100*1 + 50*2)/1e6
        assert float(record.cost) == pytest.approx(0.0002)


def test_ai_chat_service_error_returns_502(ai_client, monkeypatch):
    from app.services.ai import AiServiceError

    monkeypatch.setattr(
        "app.routes.ai.chat_once",
        lambda messages: (_ for _ in ()).throw(AiServiceError("模型服务暂时不可用，请稍后再试。")),
    )
    response = _chat_payload(ai_client, "你好")
    assert response.status_code == 502
    assert "模型服务暂时不可用" in response.get_json()["error"]


def test_ai_chat_rate_limited(ai_client, monkeypatch, app):
    monkeypatch.setattr("app.routes.ai.MAX_REQUESTS_PER_MINUTE", 3)
    with app.app_context():
        user = User.query.filter_by(email="verified@example.com").one()
        for _ in range(3):
            db.session.add(AiChatUsage(user_id=user.id, model="deepseek-v4-flash",
                                       prompt_tokens=1, completion_tokens=1,
                                       total_tokens=2, cost=0))
        db.session.commit()
    response = _chat_payload(ai_client, "你好")
    assert response.status_code == 429


def test_ai_chat_usage_model_has_no_message_column():
    """用量表只记录 token 与费用，不应包含可保存对话内容的字段。"""
    column_names = [column.name for column in AiChatUsage.__table__.columns]
    for forbidden in ("message", "question", "content", "prompt", "answer"):
        assert forbidden not in column_names


# ---------- 管理员统计 ----------

def _seed_usage(user, count=4):
    for i in range(count):
        db.session.add(AiChatUsage(
            user_id=user.id, model="deepseek-v4-flash",
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.0002,
        ))
    db.session.commit()


def test_admin_ai_usage_requires_admin(client, login):
    login("verified@example.com")
    assert client.get("/admin/ai-usage").status_code == 403
    assert client.get("/admin/ai-usage", follow_redirects=False).status_code == 403


def test_admin_ai_usage_shows_aggregates(client, login, app):
    with app.app_context():
        verified = User.query.filter_by(email="verified@example.com").one()
        _seed_usage(verified)
    login("admin@example.com")
    response = client.get("/admin/ai-usage")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "东蒙Assistant 用量统计" in body
    assert "累计提问次数" in body
    # 4 条记录：累计提问 4，总 tokens 600，费用 0.0008
    assert ">4<" in body.replace(" ", "").replace("\n", "")
    assert "600" in body
    assert "0.0008" in body
    assert "verified@example.com" in body


def test_admin_ai_usage_empty_state(client, login):
    login("admin@example.com")
    response = client.get("/admin/ai-usage")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "东蒙Assistant 还没有调用记录" in body
