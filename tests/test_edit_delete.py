"""发布后可编辑、软删除相关测试。"""
from app.extensions import db
from app.majors import OTHER
from app.models import Comment, EnglishResource, Post, User

ENGLISH_CONTENT = "这是一段用于自动化测试的学习经验正文内容，超过二十个字符。"


def _add_english(app, title, author_id, status="published"):
    with app.app_context():
        item = EnglishResource(title=title, content=ENGLISH_CONTENT, category="学术写作",
                               difficulty="入门", status=status, author_id=author_id)
        item.set_major("general")
        db.session.add(item)
        db.session.commit()
        return item.id


def test_author_edit_post_reenters_review(client, app, login):
    login("verified@example.com")
    response = client.post("/posts/1/edit", data={
        "title": "演示信息：学习搭子（已修改）",
        "category": "学习搭子",
        "content": "<p>这是修改后的帖子正文内容，等待重新审核。</p>",
        "is_anonymous": "y",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        post = db.session.get(Post, 1)
        assert post.status == "pending"
        assert "已修改" in post.title
        assert post.content == "<p>这是修改后的帖子正文内容，等待重新审核。</p>"
    assert app.test_client().get("/posts/1").status_code == 404


def test_admin_edit_post_stays_approved(client, app, login):
    login("admin@example.com")
    client.post("/posts/1/edit", data={
        "title": "演示信息：学习搭子（管理员改）",
        "category": "学习搭子",
        "content": "<p>管理员修改后的正文内容保持公开。</p>",
    })
    with app.app_context():
        assert db.session.get(Post, 1).status == "approved"


def test_non_author_cannot_edit_or_delete_post(app, client, login):
    with app.app_context():
        other = User(nickname="另一位学生", email="other@example.com", enrollment_year=2026,
                     role="student", verification_status="verified")
        other.set_major(OTHER)
        other.set_password("Password123!")
        db.session.add(other)
        db.session.commit()
    login("other@example.com")
    assert client.get("/posts/1/edit").status_code == 403
    assert client.post("/posts/1/delete").status_code == 403


def test_author_delete_post_hides_from_public(client, app, login):
    login("verified@example.com")
    client.post("/posts/1/delete", follow_redirects=True)
    with app.app_context():
        assert db.session.get(Post, 1).status == "hidden"
    guest = app.test_client()
    assert guest.get("/posts/1").status_code == 404
    assert "演示信息" not in guest.get("/posts").get_data(as_text=True)


def test_admin_sees_hidden_post_in_archive(client, app, login):
    with app.app_context():
        db.session.get(Post, 1).status = "hidden"
        db.session.commit()
    login("admin@example.com")
    assert "演示信息：学习搭子" in client.get("/admin/posts").get_data(as_text=True)


def test_english_submit_records_author(client, app, login):
    login("verified@example.com")
    client.post("/english-hub/submit", data={
        "title": "英文文献阅读经验分享",
        "category": "学术写作",
        "content": ENGLISH_CONTENT,
        "major": "general",
        "difficulty": "入门",
    })
    with app.app_context():
        item = EnglishResource.query.filter_by(title="英文文献阅读经验分享").first()
        assert item is not None
        assert item.status == "pending"
        assert item.author_id is not None


def test_student_edit_english_reenters_review(client, app, login):
    login("verified@example.com")
    item_id = _add_english(app, "学习经验A", author_id=2)
    client.post(f"/english-hub/{item_id}/edit", data={
        "title": "学习经验A（已修改）",
        "category": "学术写作",
        "content": ENGLISH_CONTENT,
        "major": "general",
        "difficulty": "进阶",
    }, follow_redirects=True)
    with app.app_context():
        item = db.session.get(EnglishResource, item_id)
        assert item.status == "pending"
        assert "已修改" in item.title
    assert "学习经验A（已修改）" not in app.test_client().get("/english-hub").get_data(as_text=True)


def test_admin_edit_english_stays_published(client, app, login):
    login("admin@example.com")
    item_id = _add_english(app, "学习经验B", author_id=2)
    client.post(f"/english-hub/{item_id}/edit", data={
        "title": "学习经验B（管理员改）",
        "category": "学术写作",
        "content": ENGLISH_CONTENT,
        "major": "general",
        "difficulty": "入门",
    })
    with app.app_context():
        assert db.session.get(EnglishResource, item_id).status == "published"


def test_english_delete_hides_from_public(client, app, login):
    login("verified@example.com")
    item_id = _add_english(app, "学习经验C", author_id=2)
    client.post(f"/english-hub/{item_id}/delete")
    assert "学习经验C" not in app.test_client().get("/english-hub").get_data(as_text=True)
    with app.app_context():
        assert db.session.get(EnglishResource, item_id).status == "hidden"


def test_author_edits_and_deletes_comment(client, app, login):
    login("verified@example.com")
    with app.app_context():
        comment = Comment(post_id=1, author_id=2, content="这是一条评论内容。")
        db.session.add(comment)
        db.session.commit()
        comment_id = comment.id
    response = client.post(f"/posts/comments/{comment_id}/edit", data={"content": "修改后的评论内容。"},
                           follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Comment, comment_id).content == "修改后的评论内容。"
    client.post(f"/posts/comments/{comment_id}/delete")
    assert "修改后的评论内容" not in app.test_client().get("/posts/1").get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Comment, comment_id).status == "hidden"


def test_author_sees_edit_delete_buttons_on_detail(client, login):
    login("verified@example.com")
    text = client.get("/posts/1").get_data(as_text=True)
    assert "编辑" in text
    assert "/posts/1/delete" in text
