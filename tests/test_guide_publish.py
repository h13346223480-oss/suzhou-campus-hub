from app.models import Guide, Post


def test_admin_post_is_published_without_review(client, app, login):
    login("admin@example.com")
    response = client.post("/posts/create", data={
        "title": "管理员直发信息：迎新安排",
        "category": "校园求助",
        "content": "<p>管理员发布的迎新安排正文内容。</p>",
    })
    assert response.status_code == 302
    with app.app_context():
        post = Post.query.filter(Post.title.contains("管理员直发信息")).first()
        assert post is not None
        assert post.status == "approved"


def test_student_post_still_requires_review(client, app, login):
    login("verified@example.com")
    client.post("/posts/create", data={
        "title": "普通学生信息：求学习搭子",
        "category": "学习搭子",
        "content": "<p>普通学生发布的正文内容。</p>",
    })
    with app.app_context():
        post = Post.query.filter(Post.title.contains("普通学生信息")).first()
        assert post.status == "pending"


def test_guest_sees_publish_buttons_with_login_prompt(client):
    posts_page = client.get("/posts")
    assert posts_page.status_code == 200
    text = posts_page.get_data(as_text=True)
    assert "发布信息" in text
    assert "请先登录后再发布" in text
    english_page = client.get("/english-hub")
    assert english_page.status_code == 200
    text = english_page.get_data(as_text=True)
    assert "提交学习经验" in text
    assert "请先登录后再发布" in text


def test_logged_in_unverified_user_sees_publish_button(client, login):
    login("pending@example.com")
    assert "发布信息" in client.get("/posts").get_data(as_text=True)


def test_guest_cannot_open_guide_create(client):
    assert client.get("/guides/create").status_code == 302


def test_non_admin_cannot_open_guide_create(client, login):
    login("verified@example.com")
    assert client.get("/guides/create").status_code == 403


def test_admin_creates_rich_text_guide(client, app, login):
    login("admin@example.com")
    response = client.post("/guides/create", data={
        "title": "新生报到流程详解：测试指南",
        "category": "报到指南",
        "summary": "报到当天步骤与材料清单。",
        "content": "<p>报到流程第一步，<strong>携带材料</strong>。</p>",
    })
    assert response.status_code == 302
    with app.app_context():
        guide = Guide.query.filter(Guide.title.contains("新生报到流程详解")).first()
        assert guide is not None
        assert guide.status == "published"
        assert guide.slug.startswith("guide-")
        assert "<strong>" in guide.content
        detail = client.get(f"/guides/{guide.slug}")
        assert detail.status_code == 200
        assert "<strong>携带材料</strong>" in detail.get_data(as_text=True)
