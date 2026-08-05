import json
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, current_app, flash, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Survey, SurveyAccessLog, SurveyAnswer, SurveyResponse, SurveyResponseAudit
from app.services.surveys import (availability, device_type, response_audit_details, safe_source,
                                  validate_submission)

bp = Blueprint("surveys", __name__)
ANON_COOKIE = "survey_anonymous_token"


def get_anonymous_token():
    return request.cookies.get(ANON_COOKIE) or uuid4().hex


def existing_response(survey, anonymous_token):
    if survey.allow_repeat:
        return None
    query = SurveyResponse.query.filter_by(survey_id=survey.id, is_valid=True)
    if current_user.is_authenticated:
        return query.filter_by(user_id=current_user.id).first()
    return query.filter_by(anonymous_token=anonymous_token).first()


def set_anonymous_cookie(response, token):
    response.set_cookie(
        ANON_COOKIE,
        token,
        max_age=31536000,
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
        httponly=True,
        samesite="Lax",
    )
    return response


@bp.route("/s/<slug>", methods=["GET", "POST"])
def fill(slug):
    survey = Survey.query.filter_by(slug=slug).first_or_404()
    is_admin_preview = current_user.is_authenticated and current_user.is_admin
    if not current_app.config["FEATURE_SURVEYS_PUBLIC"] and not (
        current_user.is_authenticated and current_user.is_admin
    ):
        return render_template("surveys/unavailable.html", survey=survey, state="disabled"), 403
    if survey.require_login and not current_user.is_authenticated:
        flash("这份调查需要登录后填写。", "warning")
        return redirect(url_for("auth.login", next=request.full_path))
    if current_user.is_authenticated and not current_user.is_admin and not current_user.is_verified:
        flash("当前账号的校园社区权限不可用，请联系平台管理员。", "warning")
        return redirect(url_for("main.profile"))
    if not survey.allow_anonymous and not current_user.is_authenticated:
        flash("这份调查不接受匿名答卷，请先登录。", "warning")
        return redirect(url_for("auth.login", next=request.full_path))

    state = availability(survey)
    if state == "draft" and not is_admin_preview:
        return render_template("errors/404.html"), 404
    if state != "open" and not is_admin_preview:
        return render_template("surveys/unavailable.html", survey=survey, state=state)

    token = get_anonymous_token()
    source = safe_source(request.args.get("source") or request.form.get("source"))
    existing = existing_response(survey, token)
    if request.method == "GET":
        db.session.add(SurveyAccessLog(survey_id=survey.id, anonymous_token=token, source=source))
        db.session.commit()
    if existing and not survey.allow_edit:
        response = make_response(render_template("surveys/already_submitted.html", survey=survey))
        return set_anonymous_cookie(response, token)

    errors = {}
    if request.method == "POST" and state == "open" and not is_admin_preview:
        answers, errors = validate_submission(survey, request.form)
        if not errors:
            completion = request.form.get("completion_seconds", type=int)
            completion = min(max(completion or 0, 0), 86400)
            if existing and survey.allow_edit:
                record = existing
                audit_action = "edited"
                for old_answer in list(record.answers):
                    db.session.delete(old_answer)
                record.submitted_at = datetime.now(timezone.utc)
                record.source = source
                record.completion_seconds = completion
            else:
                audit_action = "created"
                record = SurveyResponse(
                    survey_id=survey.id,
                    user_id=current_user.id if current_user.is_authenticated else None,
                    anonymous_token=None if current_user.is_authenticated else token,
                    source=source,
                    device_type=device_type(request.headers.get("User-Agent")),
                    completion_seconds=completion,
                )
                db.session.add(record)
                db.session.flush()
            for question, answer_text, answer_json in answers:
                db.session.add(SurveyAnswer(response_id=record.id, question_id=question.id,
                                            answer_text=answer_text, answer_json=answer_json))
            db.session.flush()
            db.session.add(SurveyResponseAudit(
                survey_id=survey.id,
                response_id=record.id,
                actor_id=current_user.id if current_user.is_authenticated else None,
                action=audit_action,
                previous_status=record.validity_status if audit_action == "edited" else None,
                new_status=record.validity_status,
                details_json=response_audit_details(record, [question.id for question, _, _ in answers]),
            ))
            db.session.commit()
            response = redirect(url_for("surveys.thanks", slug=survey.slug))
            return set_anonymous_cookie(response, token)
        flash("请检查标出的题目后重新提交。", "danger")

    initial = response_values(existing) if existing else {}
    response = make_response(render_template("surveys/fill.html", survey=survey, errors=errors, source=source,
                                             state="preview" if is_admin_preview else state,
                                             admin_preview=is_admin_preview, initial=initial))
    return set_anonymous_cookie(response, token)


def response_values(record):
    values = {}
    for answer in record.answers:
        key = f"q_{answer.question_id}"
        if answer.answer_text is not None:
            values[key] = answer.answer_text
        elif answer.answer_json:
            try:
                data = json.loads(answer.answer_json)
            except ValueError:
                continue
            values[key] = data
    return values


@bp.route("/s/<slug>/thanks")
def thanks(slug):
    survey = Survey.query.filter_by(slug=slug).first_or_404()
    is_admin = current_user.is_authenticated and current_user.is_admin
    if availability(survey) == "draft" and not is_admin:
        return render_template("errors/404.html"), 404
    return render_template("surveys/thanks.html", survey=survey)


@bp.route("/surveys/mine")
@login_required
def mine():
    responses = SurveyResponse.query.filter_by(user_id=current_user.id, is_valid=True).order_by(
        SurveyResponse.submitted_at.desc()).all()
    return render_template("surveys/mine.html", responses=responses)
