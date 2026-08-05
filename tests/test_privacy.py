def test_privacy_page_uses_current_collection_and_access_copy(client):
    response = client.get("/privacy")

    assert response.status_code == 200
    assert "注册时，我们会收集用户主动填写的邮箱、昵称、专业和入学年份" in response.text
    assert "部分调查可能设置选填的联系方式题目" in response.text
    assert "调查答卷不会向其他普通用户公开" in response.text
    assert "用户密码使用安全哈希方式保存，不以明文形式存储" in response.text
    assert "不得擅自出售或用于无关营销" in response.text


def test_privacy_page_has_no_tutoring_or_manual_matching_copy(client):
    response = client.get("/privacy")

    for phrase in ("家教", "家长联系方式", "人工匹配"):
        assert phrase not in response.text


def test_about_page_describes_current_first_stage_modules(client):
    response = client.get("/about")

    assert response.status_code == 200
    assert "新生指南、校园地图、信息广场、全英课堂助手、学习资源和校园互助" in response.text
    assert "家教需求撮合" not in response.text
