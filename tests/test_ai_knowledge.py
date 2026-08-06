"""AI 知识库：管理员增删改查、检索注入、文章自动收集与接口上下文注入的自动化测试。"""
import pytest

from app.extensions import db
from app.models import AiKnowledge, Guide, Post, User
from app.services.ai import build_chat_messages, collect_article_blocks, collect_knowledge_context


def _make_entry(app, title="新生报到需要哪些材料？", content="携带录取通知书、身份证与一寸照片。", keywords="报到, 材料, 录取通知书", is_active=True):
    with app.app_context():
        entry = AiKnowledge(title=title, content=content, keywords=keywords, is_active=is_active)
        db.session.add(entry)
        db.session.commit()
        return entry.id


# ---------- 权限 ----------

def test_admin_list_200(app, client, login):
    login("admin@example.com")
    response = client.get("/admin/ai-knowledge")
    assert response.status_code == 200
    assert "AI 知识库管理" in response.get_data(as_text=True)


def test_student_forbidden(app, client, login):
    login("verified@example.com")
    assert client.get("/admin/ai-knowledge").status_code == 403


# ---------- 新建 ----------

def test_create_requires_title(app, client, login):
    login("admin@example.com")
    response = client.post("/admin/ai-knowledge/create", data={"title": "", "content": "内容", "keywords": ""},
                           follow_redirects=True)
    with app.app_context():
        assert AiKnowledge.query.count() == 0
    assert "请填写有效的标题" in response.get_data(as_text=True)


def test_create_rejects_html(app, client, login):
    login("admin@example.com")
    response = client.post("/admin/ai-knowledge/create",
                           data={"title": "<script>alert(1)</script>", "content": "内容", "keywords": ""},
                           follow_redirects=True)
    with app.app_context():
        assert AiKnowledge.query.count() == 0
    assert "不含 HTML" in response.get_data(as_text=True)


def test_create_requires_content(app, client, login):
    login("admin@example.com")
    response = client.post("/admin/ai-knowledge/create", data={"title": "标题", "content": "", "keywords": ""},
                           follow_redirects=True)
    with app.app_context():
        assert AiKnowledge.query.count() == 0
    assert "请填写有效的内容" in response.get_data(as_text=True)


def test_create_success(app, client, login):
    login("admin@example.com")
    response = client.post("/admin/ai-knowledge/create",
                           data={"title": "报到材料", "content": "携带录取通知书、身份证与一寸照片。",
                                 "keywords": "报到, 材料", "is_active": "on"},
                           follow_redirects=True)
    with app.app_context():
        entry = AiKnowledge.query.filter_by(title="报到材料").first()
        assert entry is not None
        assert entry.is_active is True
    assert "知识条目已添加" in response.get_data(as_text=True)


# ---------- 编辑 / 启停 / 删除 ----------

def test_edit_updates(app, client, login):
    entry_id = _make_entry(app)
    login("admin@example.com")
    response = client.post(f"/admin/ai-knowledge/{entry_id}/edit",
                           data={"title": "报到材料（更新）", "content": "新内容", "keywords": "报到", "is_active": "on"},
                           follow_redirects=True)
    with app.app_context():
        entry = db.session.get(AiKnowledge, entry_id)
        assert entry.title == "报到材料（更新）"
        assert entry.content == "新内容"
    assert "知识条目已更新" in response.get_data(as_text=True)


def test_toggle_flips_active(app, client, login):
    entry_id = _make_entry(app)
    login("admin@example.com")
    client.post(f"/admin/ai-knowledge/{entry_id}/toggle")
    with app.app_context():
        assert db.session.get(AiKnowledge, entry_id).is_active is False
    client.post(f"/admin/ai-knowledge/{entry_id}/toggle")
    with app.app_context():
        assert db.session.get(AiKnowledge, entry_id).is_active is True


def test_delete_removes(app, client, login):
    entry_id = _make_entry(app)
    login("admin@example.com")
    response = client.post(f"/admin/ai-knowledge/{entry_id}/delete", follow_redirects=True)
    with app.app_context():
        assert AiKnowledge.query.count() == 0
    assert "知识条目已删除" in response.get_data(as_text=True)


# ---------- 检索与上下文注入 ----------

def test_context_matches_by_keyword(app):
    _make_entry(app, title="报到材料", content="携带录取通知书与身份证。", keywords="报到, 材料")
    _make_entry(app, title="食堂营业时间", content="早餐 7:00-9:00，午餐 11:00-13:00。", keywords="食堂, 饭堂")
    with app.app_context():
        hits = collect_knowledge_context("食堂中午几点开门")
        assert [h.title for h in hits] == ["食堂营业时间"]
        assert collect_knowledge_context("报到要带什么")[0].title == "报到材料"
        # 不匹配时返回空
        assert collect_knowledge_context("附近有什么快递点") == []


def test_context_matches_by_title_substring(app):
    _make_entry(app, title="如何完成学生认证", content="在个人中心上传校园卡照片等待审核。", keywords="")
    with app.app_context():
        hits = collect_knowledge_context("学生认证怎么弄")
        assert [h.title for h in hits] == ["如何完成学生认证"]


def test_context_excludes_inactive(app):
    entry_id = _make_entry(app, title="宿舍安排", content="2026 级本科生入住 2 号楼。", keywords="宿舍")
    with app.app_context():
        db.session.get(AiKnowledge, entry_id).is_active = False
        db.session.commit()
        assert collect_knowledge_context("宿舍在哪") == []


def test_chat_injects_context_when_matched(app, client, login, monkeypatch):
    _make_entry(app, title="报到材料", content="携带录取通知书与身份证。", keywords="报到, 材料")
    captured = {}

    def fake_chat_once(messages):
        captured["messages"] = messages
        return "按东蒙Hub 的资料回答。", {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}

    monkeypatch.setattr("app.routes.ai.chat_once", fake_chat_once)
    login("verified@example.com")
    response = client.post("/api/ai/chat", json={"message": "新生报到要带什么材料？"})
    assert response.status_code == 200
    system_contents = [m["content"] for m in captured["messages"] if m["role"] == "system"]
    assert any("携带录取通知书与身份证" in c for c in system_contents)


def test_chat_omits_context_when_unmatched(app, client, login, monkeypatch):
    _make_entry(app, title="报到材料", content="携带录取通知书与身份证。", keywords="报到, 材料")
    captured = {}

    def fake_chat_once(messages):
        captured["messages"] = messages
        return "不知道。", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    monkeypatch.setattr("app.routes.ai.chat_once", fake_chat_once)
    login("verified@example.com")
    response = client.post("/api/ai/chat", json={"message": "今天天气怎么样"})
    assert response.status_code == 200
    system_contents = [m["content"] for m in captured["messages"] if m["role"] == "system"]
    assert all("携带录取通知书" not in c for c in system_contents)
    assert len(system_contents) == 1  # 仅基础系统提示词


def test_build_messages_has_user_message(app):
    _make_entry(app, title="报到材料", content="携带录取通知书与身份证。", keywords="报到")
    with app.app_context():
        messages = build_chat_messages("报到要带什么")
        assert messages[-1] == {"role": "user", "content": "报到要带什么"}
        assert messages[0]["role"] == "system"


# ---------- 文章自动收集 ----------

def test_article_collects_approved_post(app):
    # conftest 已种子化一条已审核帖子：演示信息：学习搭子
    with app.app_context():
        hits = collect_article_blocks("学习搭子")
        assert any(label == "社区帖子" and "演示信息" in title for label, title, _ in hits)


def test_article_collects_published_guide(app):
    with app.app_context():
        db.session.add(Guide(title="食堂指南", slug="canteen-guide-test", summary="食堂营业时间",
                             content="食堂营业时间为 7:00-21:00，二楼设有清真窗口。", category="食堂", status="published"))
        db.session.commit()
        hits = collect_article_blocks("食堂营业时间")
        assert any(label == "新生指南" and title == "食堂指南" for label, title, _ in hits)


def test_article_excludes_pending_or_rejected(app):
    with app.app_context():
        author = User.query.filter_by(email="verified@example.com").first()
        db.session.add_all([
            Post(author_id=author.id, title="待审核帖子", content="独门情报：周三食堂麻辣香锅特价。",
                 category="校园生活", status="pending"),
            Post(author_id=author.id, title="被拒帖子", content="麻辣香锅特价情报。", category="校园生活", status="rejected"),
        ])
        db.session.commit()
        titles = [title for _, title, _ in collect_article_blocks("麻辣香锅特价")]
        assert "待审核帖子" not in titles
        assert "被拒帖子" not in titles


def test_article_excerpt_truncated(app):
    long_content = "课程安排" * 400  # 1600 字
    with app.app_context():
        author = User.query.filter_by(email="verified@example.com").first()
        db.session.add(Post(author_id=author.id, title="长文测试", content=long_content,
                            category="校园生活", status="approved"))
        db.session.commit()
        hits = collect_article_blocks("长文测试")
        assert hits and hits[0][0] == "社区帖子"
        excerpt = hits[0][2]
        assert excerpt.endswith("…")
        assert len(excerpt) <= 501


def test_article_respects_limit(app):
    with app.app_context():
        author = User.query.filter_by(email="verified@example.com").first()
        for index in range(5):
            db.session.add(Post(author_id=author.id, title=f"限流测试文章{index}",
                                content=f"学习搭子 变体{index} 的内容。", category="校园生活", status="approved"))
        db.session.commit()
        hits = collect_article_blocks("学习搭子")
        assert len(hits) == 3


def test_context_prefers_exact_keyword_over_common_words(app):
    # 回归：提问含“宿舍/床铺/尺寸”时应优先命中“床铺尺寸”条目，而不是被“宿舍/多少”等通用词条目挤掉
    _make_entry(app, title="不同宿舍的床铺尺寸是多少？", content="床铺尺寸195x95或195x85厘米。", keywords="床铺, 尺寸")
    _make_entry(app, title="宿管阿姨什么时候查宿舍？", content="每周查一次，白天查。", keywords="查宿舍, 宿管")
    _make_entry(app, title="大学一节课多久？一天多少节课？", content="一节课45分钟。", keywords="一节课, 课时")
    with app.app_context():
        hits = collect_knowledge_context("宿舍床铺尺寸是多少厘米？")
        assert hits and hits[0].title == "不同宿舍的床铺尺寸是多少？"
        assert "宿管阿姨" not in [h.title for h in hits]


def test_chat_injects_article_context(app, client, login, monkeypatch):
    captured = {}

    def fake_chat_once(messages):
        captured["messages"] = messages
        return "ok", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    monkeypatch.setattr("app.routes.ai.chat_once", fake_chat_once)
    login("verified@example.com")
    response = client.post("/api/ai/chat", json={"message": "学习搭子"})
    assert response.status_code == 200
    system_contents = [m["content"] for m in captured["messages"] if m["role"] == "system"]
    assert any("演示信息" in c for c in system_contents)
