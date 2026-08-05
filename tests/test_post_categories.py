# -*- coding: utf-8 -*-
"""帖子分类管理测试"""
from app.extensions import db
from app.models import Post, PostCategory, User


def test_categories_page_admin_only(client):
    # 未登录访问会被重定向到登录页
    resp = client.get("/admin/categories")
    assert resp.status_code in (302, 403)


def test_categories_page_admin(client, login):
    login("admin@example.com")
    resp = client.get("/admin/categories")
    assert resp.status_code == 200
    assert "美食推荐" in resp.text  # 内置分类含美食推荐


def test_food_recommendation_in_post_page(client):
    resp = client.get("/posts")
    assert "美食推荐" in resp.text


def test_add_custom_category(client, login):
    login("admin@example.com")
    resp = client.post("/admin/categories", data={"action": "add", "name": "桌游活动"}, follow_redirects=True)
    assert "已添加" in resp.text
    # 自定义分类出现在信息广场筛选与发布选择中
    resp2 = client.get("/posts")
    assert "桌游活动" in resp2.text
    resp3 = client.get("/posts/create")
    assert "桌游活动" in resp3.text


def test_duplicate_custom_category_rejected(client, login):
    login("admin@example.com")
    client.post("/admin/categories", data={"action": "add", "name": "桌游活动"}, follow_redirects=True)
    resp = client.post("/admin/categories", data={"action": "add", "name": "桌游活动"}, follow_redirects=True)
    assert "已存在" in resp.text


def test_builtin_duplicate_rejected(client, login):
    login("admin@example.com")
    resp = client.post("/admin/categories", data={"action": "add", "name": "美食推荐"}, follow_redirects=True)
    assert "已存在" in resp.text


def test_empty_name_rejected(client, login):
    login("admin@example.com")
    resp = client.post("/admin/categories", data={"action": "add", "name": ""}, follow_redirects=True)
    assert "不能为空" in resp.text


def test_delete_unused_category(client, login, app):
    login("admin@example.com")
    with app.app_context():
        cat = PostCategory(name="临时分类")
        db.session.add(cat)
        db.session.commit()
        cat_id = cat.id
    resp = client.post("/admin/categories", data={"action": "delete", "category_id": cat_id}, follow_redirects=True)
    assert "已删除" in resp.text


def test_delete_in_use_category_rejected(client, login, app):
    login("admin@example.com")
    with app.app_context():
        author = User.query.filter_by(email="verified@example.com").first()
        cat = PostCategory(name="社团活动")
        db.session.add(cat)
        db.session.flush()
        db.session.add(Post(author_id=author.id, title="社团招新", content="测试内容。", category="社团活动", status="approved"))
        db.session.commit()
        cat_id = cat.id
    resp = client.post("/admin/categories", data={"action": "delete", "category_id": cat_id}, follow_redirects=True)
    assert "已有帖子" in resp.text


def test_delete_nonexistent_category(client, login):
    login("admin@example.com")
    resp = client.post("/admin/categories", data={"action": "delete", "category_id": 9999}, follow_redirects=True)
    assert "不存在" in resp.text
