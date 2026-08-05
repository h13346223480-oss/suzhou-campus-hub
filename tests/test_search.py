from app.extensions import db
from app.models import EnglishResource, Guide


def test_global_search_matches_posts(app, client):
    resp = client.get("/search?q=" + "学习搭子")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "演示信息：学习搭子" in text


def test_global_search_matches_guides_and_resources(app, client):
    with app.app_context():
        db.session.add_all([
            Guide(title="自动化测试指南：报到流程", slug="test-guide-search", summary="报到材料清单",
                  content="报到流程与材料说明", category="报到准备", status="published"),
            EnglishResource(title="自动化测试资源：概率论", category="课程经验",
                            content="概率论与数理统计学习笔记", major="机器人工程",
                            major_code="robotics_engineering", difficulty="入门", status="published"),
        ])
        db.session.commit()
    resp = client.get("/search?q=" + "自动化测试")
    assert resp.status_code == 200
    text = resp.get_data(as_text=True)
    assert "自动化测试指南：报到流程" in text
    assert "自动化测试资源：概率论" in text


def test_global_search_no_match(app, client):
    resp = client.get("/search?q=" + "不存在的关键词xyz")
    assert resp.status_code == 200
    assert "没有找到与" in resp.get_data(as_text=True)


def test_global_search_empty_query(app, client):
    resp = client.get("/search")
    assert resp.status_code == 200
    assert "输入关键词即可搜索" in resp.get_data(as_text=True)
