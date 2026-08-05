from app.extensions import db
from app.models import Guide


def test_admin_can_edit_guide_and_stays_published(client, app, login):
    login("admin@example.com")
    client.post("/guides/create", data={
        "title": "编辑测试指南",
        "category": "报到指南",
        "summary": "原标题摘要",
        "content": "<p>原标题正文内容。</p>",
    })
    with app.app_context():
        slug = Guide.query.filter_by(title="编辑测试指南").one().slug
    response = client.get(f"/guides/{slug}/edit")
    assert response.status_code == 200
    assert "编辑新生指南" in response.get_data(as_text=True)
    response = client.post(f"/guides/{slug}/edit", data={
        "title": "编辑后的标题",
        "category": "报到指南",
        "summary": "更新后的摘要",
        "content": "<p>更新后的正文内容。</p>",
    })
    assert response.status_code == 302
    with app.app_context():
        guide = Guide.query.filter_by(slug=slug).one()
        assert guide.title == "编辑后的标题"
        assert guide.status == "published"
    detail = client.get(f"/guides/{slug}")
    assert "更新后的正文内容" in detail.get_data(as_text=True)


def test_non_admin_cannot_edit_or_delete_guide(client, login):
    with client.application.app_context():
        guide = Guide(title="权限测试指南", slug="perm-guide", summary="摘要",
                      content="<p>正文内容</p>", category="报到指南", status="published")
        db.session.add(guide)
        db.session.commit()
        slug = guide.slug
    login("verified@example.com")
    assert client.get(f"/guides/{slug}/edit").status_code == 403
    assert client.post(f"/guides/{slug}/delete").status_code == 403


def test_admin_delete_guide_hides_public_but_archives_in_backend(client, login):
    with client.application.app_context():
        guide = Guide(title="删除测试指南", slug="del-guide", summary="摘要",
                      content="<p>正文内容</p>", category="报到指南", status="published")
        db.session.add(guide)
        db.session.commit()
        slug = guide.slug
    assert "删除测试指南" in client.get("/guides").get_data(as_text=True)
    login("admin@example.com")
    response = client.post(f"/guides/{slug}/delete")
    assert response.status_code == 302
    with client.application.app_context():
        assert Guide.query.filter_by(slug=slug).one().status == "hidden"
    assert "删除测试指南" not in client.get("/guides").get_data(as_text=True)
    page = client.get("/admin/content")
    assert "删除测试指南" in page.get_data(as_text=True)


def test_guide_page_shows_admin_edit_delete_buttons(client, login):
    with client.application.app_context():
        guide = Guide(title="按钮测试指南", slug="btn-guide", summary="摘要",
                      content="<p>正文内容</p>", category="报到指南", status="published")
        db.session.add(guide)
        db.session.commit()
        slug = guide.slug
    assert client.get(f"/guides/{slug}").get_data(as_text=True).count("编辑") == 0
    login("admin@example.com")
    index_text = client.get("/guides").get_data(as_text=True)
    assert "按钮测试指南" in index_text
    assert "编辑" in index_text
    assert "删除" in index_text
    detail_text = client.get(f"/guides/{slug}").get_data(as_text=True)
    assert "编辑" in detail_text
    assert "删除" in detail_text
