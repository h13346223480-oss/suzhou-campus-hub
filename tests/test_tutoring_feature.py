def test_home_uses_student_platform_positioning_and_six_core_entries(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "首届本科生的信息、学习与校园互助平台" in response.text
    for label in ["新生指南", "校园地图", "信息广场", "全英课堂助手", "学习资源", "校园互助"]:
        assert label in response.text
    assert "家教服务" not in response.text
    assert "提交家教需求" not in response.text


def test_tutoring_navigation_is_hidden_by_default(client):
    response = client.get("/")
    assert 'href="/tutoring"' not in response.text


def test_public_tutor_list_is_hidden_when_feature_disabled(client):
    assert client.get("/tutoring").status_code == 404


def test_public_tutor_request_is_hidden_when_feature_disabled(client):
    assert client.get("/tutoring/request").status_code == 404
    assert client.post("/tutoring/request", data={}).status_code == 404


def test_hidden_tutoring_post_category_is_not_exposed(client, login, app):
    from app.extensions import db
    from app.models import Post, User

    with app.app_context():
        author = User.query.filter_by(email="verified@example.com").one()
        post = Post(author_id=author.id, title="隐藏家教帖子", content="该内容仅用于验证功能开关隔离。",
                    category="家教相关", status="approved")
        db.session.add(post)
        db.session.commit()
        post_id = post.id
    login("verified@example.com")
    listing = client.get("/posts")
    assert "家教相关" not in listing.text
    assert "隐藏家教帖子" not in listing.text
    assert client.get(f"/posts/{post_id}").status_code == 404
    create_page = client.get("/posts/create")
    assert "家教相关" not in create_page.text


def test_normal_student_cannot_open_hidden_tutor_pages(client, login):
    login("verified@example.com")
    assert client.get("/tutoring").status_code == 404
    assert client.get("/tutoring/request").status_code == 404


def test_admin_can_open_hidden_tutor_pages(client, login):
    login("admin@example.com")
    assert client.get("/tutoring").status_code == 200
    assert client.get("/tutoring/request").status_code == 200


def test_verified_student_keeps_low_profile_teacher_application(client, login):
    login("verified@example.com")
    response = client.get("/profile")
    assert response.status_code == 200
    assert "家教模块处于隐藏开发状态" in response.text
    assert "申请成为家教老师" in response.text
    assert 'class="btn secondary" href="/tutoring/profile"' not in response.text


def test_tutoring_can_be_reenabled_with_feature_flag(client, app):
    app.config["FEATURE_TUTORING_PUBLIC"] = True
    response = client.get("/tutoring")
    assert response.status_code == 200
    home = client.get("/")
    assert 'href="/tutoring"' in home.text
