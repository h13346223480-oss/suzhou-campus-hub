from io import BytesIO

from PIL import Image

from app.models import Post


def test_post_accepts_rich_text(client, app, login):
    login("verified@example.com")
    response = client.post("/posts/create", data={
        "title": "富文本测试信息：寻找学习搭子",
        "category": "学习搭子",
        "content": "<p>这是一段<strong>加粗</strong>与<em>斜体</em>的正文内容。</p>",
    })
    assert response.status_code == 302
    with app.app_context():
        post = Post.query.order_by(Post.id.desc()).first()
        assert "<strong>" in post.content
        assert "<em>" in post.content


def test_script_tags_are_stripped_from_post(client, app, login):
    login("verified@example.com")
    client.post("/posts/create", data={
        "title": "恶意脚本测试信息",
        "category": "校园求助",
        "content": "<p>正常内容<script>alert(1)</script></p>",
    })
    with app.app_context():
        post = Post.query.order_by(Post.id.desc()).first()
        assert "script" not in post.content
        assert "正常内容" in post.content


def test_javascript_protocol_is_removed(client, app, login):
    login("verified@example.com")
    client.post("/posts/create", data={
        "title": "恶意图片测试信息",
        "category": "校园求助",
        "content": '<p>其余正文内容</p><img src="javascript:alert(1)">',
    })
    with app.app_context():
        post = Post.query.order_by(Post.id.desc()).first()
        assert "javascript:" not in post.content


def test_rich_text_anchor_is_hardened(client, app, login):
    login("verified@example.com")
    client.post("/posts/create", data={
        "title": "外链测试信息",
        "category": "校园求助",
        "content": '<p>请看<a href="https://example.com">外部链接</a></p>',
    })
    with app.app_context():
        post = Post.query.order_by(Post.id.desc()).first()
        assert 'target="_blank"' in post.content
        assert "noopener" in post.content


def test_content_stripped_to_empty_is_rejected(client, app, login):
    login("verified@example.com")
    client.post("/posts/create", data={
        "title": "空正文测试信息",
        "category": "校园求助",
        "content": "<script>alert(1)</script>",
    })
    with app.app_context():
        post = Post.query.filter(Post.title.contains("空正文测试信息")).first()
        assert post is None


def test_upload_requires_login(client):
    response = client.post("/posts/upload-image", data={})
    assert response.status_code == 302


def test_upload_rejects_invalid_type(client, login):
    login("verified@example.com")
    response = client.post("/posts/upload-image",
                           data={"image": (BytesIO(b"<svg onload=alert(1)></svg>"), "bad.svg")},
                           content_type="multipart/form-data")
    assert response.status_code == 400


def test_upload_rejects_fake_image(client, login):
    login("verified@example.com")
    response = client.post("/posts/upload-image",
                           data={"image": (BytesIO(b"not-a-real-image"), "fake.png")},
                           content_type="multipart/form-data")
    assert response.status_code == 400


def test_upload_accepts_real_image(client, app, login, tmp_path):
    app.config["UPLOAD_FOLDER"] = tmp_path
    login("verified@example.com")
    buf = BytesIO()
    Image.new("RGB", (6, 6), "green").save(buf, format="PNG")
    buf.seek(0)
    response = client.post("/posts/upload-image",
                           data={"image": (buf, "photo.png")},
                           content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.get_json()["location"].startswith("/static/uploads/")
    assert len(list(tmp_path.iterdir())) == 1
