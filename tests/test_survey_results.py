import json
from datetime import datetime, timezone

from app.extensions import db
from app.models import (
    Survey,
    SurveyAccessLog,
    SurveyAnswer,
    SurveyAnswerTag,
    SurveyDecisionOverride,
    SurveyOption,
    SurveyQuestion,
    SurveyResponse,
    SurveyResponseAudit,
    User,
)


def make_results_survey(app):
    with app.app_context():
        admin = User.query.filter_by(role="admin").one()
        student = User.query.filter_by(email="verified@example.com").one()
        survey = Survey(
            title="调查结果专项验收",
            slug="survey-results-check",
            description="用于验收统计、标注、有效性和隐私隔离。",
            status="published",
            allow_anonymous=True,
            use_account_profile_data=True,
            created_by=admin.id,
        )
        db.session.add(survey)
        db.session.flush()

        single = SurveyQuestion(
            survey_id=survey.id,
            title="最需要的校园服务",
            question_type="single_choice",
            sort_order=1,
            validation_rules_json="{}",
        )
        multiple = SurveyQuestion(
            survey_id=survey.id,
            title="希望优先完善的内容",
            question_type="multiple_choice",
            sort_order=2,
            validation_rules_json="{}",
        )
        rating = SurveyQuestion(
            survey_id=survey.id,
            title="当前体验评分",
            question_type="rating",
            sort_order=3,
            validation_rules_json='{"min_value": 1, "max_value": 5}',
        )
        text = SurveyQuestion(
            survey_id=survey.id,
            title="其他建议",
            question_type="long_text",
            sort_order=4,
            validation_rules_json="{}",
        )
        contact = SurveyQuestion(
            survey_id=survey.id,
            title="内测联系方式",
            question_type="short_text",
            is_contact_info=True,
            sort_order=5,
            validation_rules_json="{}",
        )
        db.session.add_all([single, multiple, rating, text, contact])
        db.session.flush()
        options = [
            SurveyOption(question_id=single.id, label="学习资源", value="learning", sort_order=1),
            SurveyOption(question_id=single.id, label="校园地图", value="map", sort_order=2),
            SurveyOption(question_id=single.id, label="信息广场", value="square", sort_order=3),
            SurveyOption(question_id=multiple.id, label="学习资源", value="learning", sort_order=1),
            SurveyOption(question_id=multiple.id, label="校园地图", value="map", sort_order=2),
            SurveyOption(question_id=multiple.id, label="信息广场", value="square", sort_order=3),
        ]
        db.session.add_all(options)

        submitted = datetime(2026, 8, 1, 4, 0, tzinfo=timezone.utc)
        valid_logged = SurveyResponse(
            survey_id=survey.id,
            user_id=student.id,
            submitted_at=submitted,
            source="wechat_group",
            completion_seconds=60,
            validity_status="valid",
            is_valid=True,
        )
        valid_anonymous = SurveyResponse(
            survey_id=survey.id,
            anonymous_token="anonymous-results-test",
            submitted_at=datetime(2026, 8, 2, 4, 0, tzinfo=timezone.utc),
            source="direct",
            completion_seconds=120,
            validity_status="valid",
            is_valid=True,
        )
        invalid = SurveyResponse(
            survey_id=survey.id,
            anonymous_token="invalid-results-test",
            submitted_at=datetime(2026, 8, 2, 5, 0, tzinfo=timezone.utc),
            source="wechat_group",
            completion_seconds=30,
            validity_status="invalid",
            is_valid=False,
        )
        db.session.add_all([valid_logged, valid_anonymous, invalid])
        db.session.flush()

        add_answers(valid_logged, single, multiple, rating, text, contact,
                    "learning", ["learning", "map"], "5", "希望延长学习空间开放时间。", "wx-secret-001")
        add_answers(valid_anonymous, single, multiple, rating, text, contact,
                    "map", ["map"], "3", "希望完善校区班车信息。", "mail-secret@example.com")
        add_answers(invalid, single, multiple, rating, text, contact,
                    "learning", ["learning"], "1", "这是一条测试答卷。", "test-secret")
        db.session.add_all([
            SurveyAccessLog(survey_id=survey.id, source="wechat_group", visited_at=submitted),
            SurveyAccessLog(survey_id=survey.id, source="wechat_group", visited_at=submitted),
            SurveyAccessLog(survey_id=survey.id, source="direct", visited_at=submitted),
            SurveyAccessLog(survey_id=survey.id, source="direct", visited_at=submitted),
        ])
        db.session.commit()
        return {
            "survey_id": survey.id,
            "single_id": single.id,
            "multiple_id": multiple.id,
            "rating_id": rating.id,
            "text_id": text.id,
            "contact_id": contact.id,
            "valid_response_id": valid_logged.id,
            "anonymous_response_id": valid_anonymous.id,
            "invalid_response_id": invalid.id,
            "text_answer_id": next(answer.id for answer in valid_logged.answers if answer.question_id == text.id),
        }


def add_answers(record, single, multiple, rating, text, contact,
                single_value, multiple_values, rating_value, text_value, contact_value):
    db.session.add_all([
        SurveyAnswer(response=record, question=single, answer_text=single_value,
                     answer_json=json.dumps({"value": single_value})),
        SurveyAnswer(response=record, question=multiple, answer_text="，".join(multiple_values),
                     answer_json=json.dumps({"values": multiple_values})),
        SurveyAnswer(response=record, question=rating, answer_text=rating_value),
        SurveyAnswer(response=record, question=text, answer_text=text_value),
        SurveyAnswer(response=record, question=contact, answer_text=contact_value),
    ])


def test_statistics_cover_required_metrics_and_exclude_invalid_and_contact(client, login, app):
    ids = make_results_survey(app)
    login("admin@example.com")
    response = client.get(f"/admin/surveys/{ids['survey_id']}/stats")
    assert response.status_code == 200
    for label in ["浏览量", "提交量", "有效答卷数", "完成率", "平均填写时间", "每日提交趋势"]:
        assert label in response.text
    assert "75.0%" in response.text
    assert "90秒" in response.text
    assert "<strong>4.0</strong>平均分" in response.text
    assert "<strong>4.0</strong>中位数" in response.text
    assert "校园地图" in response.text
    assert "100.0%" in response.text
    assert "内测联系方式" not in response.text
    assert "wx-secret-001" not in response.text
    assert "这是一条测试答卷" not in response.text


def test_statistics_filters_by_major_source_date_and_login_state(client, login, app):
    ids = make_results_survey(app)
    login("admin@example.com")
    base = f"/admin/surveys/{ids['survey_id']}/stats"
    response = client.get(base + "?major=robotics_engineering&source=wechat_group&logged=yes&date_from=2026-08-01&date_to=2026-08-01")
    assert response.status_code == 200
    assert "<strong>1</strong><span>有效答卷数" in response.text
    assert "60秒" in response.text
    response = client.get(base + "?logged=no&source=direct")
    assert "<strong>1</strong><span>有效答卷数" in response.text
    assert "120秒" in response.text


def test_admin_can_tag_and_filter_text_answers(client, login, app):
    ids = make_results_survey(app)
    login("admin@example.com")
    response = client.post(
        f"/admin/surveys/{ids['survey_id']}/answers/{ids['text_answer_id']}/tags",
        data={"tag": "学习空间，开放时间"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "学习空间" in response.text
    assert "开放时间" in response.text
    with app.app_context():
        assert SurveyAnswerTag.query.filter_by(answer_id=ids["text_answer_id"]).count() == 2
    filtered = client.get(
        f"/admin/surveys/{ids['survey_id']}/text-answers/{ids['text_id']}?tag=学习空间"
    )
    assert "希望延长学习空间开放时间" in filtered.text
    assert "希望完善校区班车信息" not in filtered.text


def test_validity_change_and_delete_are_audited(client, login, app):
    ids = make_results_survey(app)
    login("admin@example.com")
    response = client.post(
        f"/admin/surveys/{ids['survey_id']}/responses/{ids['valid_response_id']}/validity",
        data={"validity_status": "test"},
        follow_redirects=True,
    )
    assert "答卷有效性已更新" in response.text
    with app.app_context():
        record = db.session.get(SurveyResponse, ids["valid_response_id"])
        assert record.validity_status == "test"
        assert record.is_valid is False
        assert SurveyResponseAudit.query.filter_by(response_id=record.id, action="validity_changed").count() == 1

    delete_url = f"/admin/surveys/{ids['survey_id']}/responses/{ids['anonymous_response_id']}/delete"
    response = client.post(delete_url, data={}, follow_redirects=True)
    assert "请在二次确认页勾选确认" in response.text
    with app.app_context():
        assert db.session.get(SurveyResponse, ids["anonymous_response_id"]) is not None
    response = client.post(delete_url, data={"confirm_delete": "yes"}, follow_redirects=True)
    assert "删除操作和非敏感元数据已写入审计记录" in response.text
    with app.app_context():
        assert db.session.get(SurveyResponse, ids["anonymous_response_id"]) is None
        audit = SurveyResponseAudit.query.filter_by(survey_id=ids["survey_id"], action="deleted").one()
        assert audit.response_id is None
        assert "mail-secret@example.com" not in audit.details_json


def test_decision_summary_uses_thresholds_and_allows_manual_override(client, login, app):
    ids = make_results_survey(app)
    login("admin@example.com")
    url = f"/admin/surveys/{ids['survey_id']}/decision-summary"
    response = client.get(url)
    assert response.status_code == 200
    assert "高优先级" in response.text
    assert "中优先级" in response.text
    assert "观察项" in response.text
    response = client.post(url, data={
        "question_id": ids["multiple_id"],
        "option_value": "map",
        "priority": "watch",
    }, follow_redirects=True)
    assert "产品决策优先级已更新" in response.text
    with app.app_context():
        override = SurveyDecisionOverride.query.filter_by(
            survey_id=ids["survey_id"], question_id=ids["multiple_id"], option_value="map"
        ).one()
        assert override.priority == "watch"


def test_anonymous_report_excludes_identity_and_contact_but_invite_export_contains_contact(client, login, app):
    ids = make_results_survey(app)
    login("admin@example.com")
    report = client.get(f"/admin/surveys/{ids['survey_id']}/anonymous-report.html")
    assert report.status_code == 200
    report_text = report.data.decode("utf-8")
    assert "内测联系方式" not in report_text
    assert "wx-secret-001" not in report_text
    assert "mail-secret@example.com" not in report_text
    assert "verified@example.com" not in report_text
    assert "认证学生" not in report_text
    assert report.headers["Cache-Control"].startswith("private, no-store")

    invite_list = client.get(f"/admin/surveys/{ids['survey_id']}/invite-list.csv")
    invite_text = invite_list.data.decode("utf-8-sig")
    assert invite_list.status_code == 200
    assert "内测联系方式" in invite_text
    assert "wx-secret-001" in invite_text
    assert "mail-secret@example.com" in invite_text


def test_normal_user_cannot_access_any_survey_result_or_sensitive_endpoint(client, login, app):
    ids = make_results_survey(app)
    login("verified@example.com")
    survey_id = ids["survey_id"]
    protected_gets = [
        f"/admin/surveys/{survey_id}/stats",
        f"/admin/surveys/{survey_id}/responses",
        f"/admin/surveys/{survey_id}/responses/{ids['valid_response_id']}",
        f"/admin/surveys/{survey_id}/responses/{ids['valid_response_id']}/delete-confirm",
        f"/admin/surveys/{survey_id}/text-answers/{ids['text_id']}",
        f"/admin/surveys/{survey_id}/decision-summary",
        f"/admin/surveys/{survey_id}/anonymous-report.html",
        f"/admin/surveys/{survey_id}/invite-list.csv",
        f"/admin/surveys/{survey_id}/export.csv",
        f"/admin/surveys/{survey_id}/export.xlsx",
    ]
    for url in protected_gets:
        assert client.get(url).status_code == 403, url
    assert client.post(
        f"/admin/surveys/{survey_id}/answers/{ids['text_answer_id']}/tags",
        data={"tag": "越权标签"},
    ).status_code == 403
    assert client.post(
        f"/admin/surveys/{survey_id}/responses/{ids['valid_response_id']}/validity",
        data={"validity_status": "invalid"},
    ).status_code == 403
    assert client.post(
        f"/admin/surveys/{survey_id}/responses/{ids['valid_response_id']}/delete",
        data={"confirm_delete": "yes"},
    ).status_code == 403
