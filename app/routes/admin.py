from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_hex
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy import or_

from app.extensions import db
from app.forms import AdminCreateUserForm, ENGLISH_CATEGORIES, GUIDE_CATEGORIES, LOCATION_CATEGORIES, POST_CATEGORIES, ResetPasswordForm
from app.majors import PENDING_CONFIRMATION, RESOURCE_MAJOR_CODES, USER_MAJOR_CODES, normalize_resource_major
from app.models import (AiChatUsage, AiKnowledge, CampusLocation, Comment, EnglishResource, Guide,
                        InviteCode, InviteRedemption, Post, PostCategory, Report, SiteStat, SurveyResponse,
                        TutorProfile, TutorRequest, User, utcnow)
from app.utils.security import admin_required, contains_html
from app.utils.uploads import save_image

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("")
@admin_required
def dashboard():
    stats = {
        "restricted_users": User.query.filter(
            User.role != "admin",
            or_(User.verification_status != "verified", User.is_active.is_(False)),
        ).count(),
        "pending_posts": Post.query.filter_by(status="pending").count(),
        "open_reports": Report.query.filter_by(status="pending").count(),
        "tutor_requests": TutorRequest.query.filter_by(status="pending").count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@bp.route("/categories", methods=["GET", "POST"])
@admin_required
def categories():
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "add":
            name = request.form.get("name", "").strip()
            if not name or len(name) > 30 or contains_html(name):
                flash("分类名称不能为空、超过 30 字或包含 HTML 标签。", "danger")
            elif name in POST_CATEGORIES or PostCategory.query.filter_by(name=name).first():
                flash("该分类已存在。", "warning")
            else:
                db.session.add(PostCategory(name=name, is_custom=True))
                db.session.commit()
                flash("自定义分类「{}」已添加。".format(name), "success")
        elif action == "delete":
            category_id = request.form.get("category_id", type=int)
            category = db.session.get(PostCategory, category_id)
            if not category:
                flash("分类不存在。", "warning")
            elif not category.is_custom:
                flash("内置分类不能删除。", "warning")
            elif Post.query.filter_by(category=category.name).first():
                flash("该分类下已有帖子，不能删除。", "warning")
            else:
                db.session.delete(category)
                db.session.commit()
                flash("自定义分类「{}」已删除。".format(category.name), "success")
        return redirect(url_for("admin.categories"))
    custom_categories = PostCategory.query.order_by(PostCategory.sort_order, PostCategory.id).all()
    return render_template("admin/categories.html", builtin_categories=POST_CATEGORIES, custom_categories=custom_categories)

@bp.route("/stats")
@admin_required
def stats():
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    site_stat = db.session.get(SiteStat, 1)
    return render_template("admin/stats.html", **{
        "total_visits": site_stat.total_visits if site_stat else 0,
        "user_total": User.query.count(),
        "user_verified": User.query.filter_by(verification_status="verified").count(),
        "user_pending": User.query.filter_by(verification_status="pending").count(),
        "user_this_month": User.query.filter(User.created_at >= month_start).count(),
        "post_total": Post.query.count(),
        "post_pending": Post.query.filter_by(status="pending").count(),
        "comment_total": Comment.query.count(),
        "guide_total": Guide.query.count(),
        "resource_total": EnglishResource.query.count(),
        "resource_pending": EnglishResource.query.filter_by(status="pending").count(),
        "location_total": CampusLocation.query.count(),
        "tutor_request_total": TutorRequest.query.count(),
        "report_pending": Report.query.filter_by(status="pending").count(),
        "survey_response_total": SurveyResponse.query.count(),
    })


def _ai_agg(query):
    row = query.with_entities(
        db.func.count(AiChatUsage.id),
        db.func.coalesce(db.func.sum(AiChatUsage.prompt_tokens), 0),
        db.func.coalesce(db.func.sum(AiChatUsage.completion_tokens), 0),
        db.func.coalesce(db.func.sum(AiChatUsage.total_tokens), 0),
        db.func.coalesce(db.func.sum(AiChatUsage.cost), 0),
    ).one()
    return {
        "requests": row[0],
        "prompt_tokens": int(row[1]),
        "completion_tokens": int(row[2]),
        "total_tokens": int(row[3]),
        "cost": float(row[4]),
    }


def _format_cost(value):
    return ("%.6f" % value).rstrip("0").rstrip(".") or "0"


def _cn_time(value):
    if value is None:
        return "-"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%m月%d日 %H:%M")


@bp.route("/ai-usage")
@admin_required
def ai_usage():
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    base = AiChatUsage.query
    totals = _ai_agg(base)
    today = _ai_agg(base.filter(AiChatUsage.created_at >= today_start))
    month = _ai_agg(base.filter(AiChatUsage.created_at >= month_start))

    per_user = (db.session.query(
        User.nickname,
        User.email,
        db.func.count(AiChatUsage.id),
        db.func.coalesce(db.func.sum(AiChatUsage.total_tokens), 0),
        db.func.coalesce(db.func.sum(AiChatUsage.cost), 0),
    )
        .join(AiChatUsage, AiChatUsage.user_id == User.id)
        .group_by(User.id)
        .order_by(db.func.coalesce(db.func.sum(AiChatUsage.total_tokens), 0).desc())
        .limit(10).all())

    daily = (db.session.query(
        db.func.date(AiChatUsage.created_at),
        db.func.count(AiChatUsage.id),
        db.func.coalesce(db.func.sum(AiChatUsage.total_tokens), 0),
        db.func.coalesce(db.func.sum(AiChatUsage.cost), 0),
    )
        .filter(AiChatUsage.created_at >= now - timedelta(days=30))
        .group_by(db.func.date(AiChatUsage.created_at))
        .order_by(db.func.date(AiChatUsage.created_at).desc())
        .all())

    recent = AiChatUsage.query.order_by(AiChatUsage.id.desc()).limit(20).all()
    return render_template(
        "admin/ai_usage.html",
        totals=totals,
        today=today,
        month=month,
        per_user=per_user,
        daily=daily,
        recent=recent,
        format_cost=_format_cost,
        cn_time=_cn_time,
    )


# ---------- AI 知识库管理 ----------

MAX_KNOWLEDGE_TITLE = 120
MAX_KNOWLEDGE_CONTENT = 4000
MAX_KNOWLEDGE_KEYWORDS = 255


def _knowledge_clean_form():
    """校验知识库表单，返回 (title, content, keywords, is_active)；失败时返回 None 并写入 flash。"""
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    keywords = request.form.get("keywords", "").strip()
    if not title or len(title) > MAX_KNOWLEDGE_TITLE or contains_html(title):
        flash("请填写有效的标题（120 字以内，不含 HTML）。", "danger")
        return None
    if not content or len(content) > MAX_KNOWLEDGE_CONTENT or contains_html(content):
        flash("请填写有效的内容（4000 字以内，不含 HTML）。", "danger")
        return None
    if len(keywords) > MAX_KNOWLEDGE_KEYWORDS or contains_html(keywords):
        flash("关键词不能超过 255 字或包含 HTML 标签。", "danger")
        return None
    return title, content, keywords, request.form.get("is_active") == "on"


@bp.route("/ai-knowledge")
@admin_required
def ai_knowledge():
    entries = AiKnowledge.query.order_by(AiKnowledge.updated_at.desc()).all()
    return render_template("admin/ai_knowledge.html", entries=entries)


@bp.route("/ai-knowledge/create", methods=["GET", "POST"])
@admin_required
def ai_knowledge_create():
    if request.method == "POST":
        cleaned = _knowledge_clean_form()
        if cleaned is None:
            return redirect(url_for("admin.ai_knowledge_create"))
        title, content, keywords, is_active = cleaned
        db.session.add(AiKnowledge(title=title, content=content, keywords=keywords, is_active=is_active))
        db.session.commit()
        flash("知识条目已添加。", "success")
        return redirect(url_for("admin.ai_knowledge"))
    return render_template("admin/ai_knowledge_form.html", entry=None)


@bp.route("/ai-knowledge/<int:knowledge_id>/edit", methods=["GET", "POST"])
@admin_required
def ai_knowledge_edit(knowledge_id):
    entry = db.get_or_404(AiKnowledge, knowledge_id)
    if request.method == "POST":
        cleaned = _knowledge_clean_form()
        if cleaned is None:
            return redirect(url_for("admin.ai_knowledge_edit", knowledge_id=entry.id))
        title, content, keywords, is_active = cleaned
        entry.title = title
        entry.content = content
        entry.keywords = keywords
        entry.is_active = is_active
        db.session.commit()
        flash("知识条目已更新。", "success")
        return redirect(url_for("admin.ai_knowledge"))
    return render_template("admin/ai_knowledge_form.html", entry=entry)


@bp.route("/ai-knowledge/<int:knowledge_id>/toggle", methods=["POST"])
@admin_required
def ai_knowledge_toggle(knowledge_id):
    entry = db.get_or_404(AiKnowledge, knowledge_id)
    entry.is_active = not entry.is_active
    db.session.commit()
    flash("知识条目已{}。".format("启用" if entry.is_active else "停用"), "success")
    return redirect(url_for("admin.ai_knowledge"))


@bp.route("/ai-knowledge/<int:knowledge_id>/delete", methods=["POST"])
@admin_required
def ai_knowledge_delete(knowledge_id):
    entry = db.get_or_404(AiKnowledge, knowledge_id)
    db.session.delete(entry)
    db.session.commit()
    flash("知识条目已删除。", "success")
    return redirect(url_for("admin.ai_knowledge"))


@bp.route("/users")
@admin_required
def users():
    major_code = request.args.get("major", "").strip()
    query = User.query
    if major_code in USER_MAJOR_CODES:
        query = query.filter_by(major_code=major_code)
    return render_template("admin/users.html", users=query.order_by(User.created_at.desc()).all(),
                           selected_major=major_code)


@bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def users_new():
    form = AdminCreateUserForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data.lower().strip(),
            nickname=form.nickname.data.strip(),
            role=form.role.data,
            verification_status="verified",
            is_active=True,
            enrollment_year=datetime.now(ZoneInfo("Asia/Shanghai")).year,
        )
        user.set_major(PENDING_CONFIRMATION)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("用户已创建。", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/users_new.html", form=form)


@bp.route("/invites", methods=["GET", "POST"])
@admin_required
def invites():
    if request.method == "POST":
        max_uses = request.form.get("max_uses", type=int)
        expires_value = request.form.get("expires_at", "").strip()
        try:
            local_expiry = datetime.fromisoformat(expires_value)
            expires_at = local_expiry.replace(tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(timezone.utc)
        except ValueError:
            expires_at = None
        if not max_uses or not 1 <= max_uses <= 1000:
            flash("最大使用次数必须在 1 到 1000 之间。", "danger")
        elif not expires_at or expires_at <= utcnow():
            flash("失效时间必须是未来的北京时间。", "danger")
        else:
            code = generate_invite_code()
            db.session.add(InviteCode(code=code, max_uses=max_uses, expires_at=expires_at, is_active=True))
            db.session.commit()
            flash("邀请码已创建。", "success")
            return redirect(url_for("admin.invites"))
    default_expiry = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=30)).replace(second=0, microsecond=0)
    return render_template(
        "admin/invites.html",
        invites=InviteCode.query.order_by(InviteCode.id.desc()).all(),
        default_expiry=default_expiry,
        display_expiry=display_expiry,
        invite_redemption_model=InviteRedemption,
    )


@bp.route("/invites/<int:invite_id>/toggle", methods=["POST"])
@admin_required
def toggle_invite(invite_id):
    invite = db.get_or_404(InviteCode, invite_id)
    invite.is_active = not invite.is_active
    db.session.commit()
    flash("邀请码状态已更新。", "success")
    return redirect(url_for("admin.invites"))


def generate_invite_code():
    while True:
        code = f"SZ-{token_hex(5).upper()}"
        if not InviteCode.query.filter_by(code=code).first():
            return code


def display_expiry(value):
    if value is None:
        return "未设置"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")


@bp.route("/users/<int:user_id>/verify", methods=["POST"])
@admin_required
def verify_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_admin:
        abort(400)
    user.verification_status = "verified"
    db.session.commit()
    flash("学生认证已通过。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@admin_required
def reset_password(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("请通过个人设置修改自己的密码。", "warning")
        return redirect(url_for("admin.users"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        db.session.commit()
        flash(f"已重置 {user.nickname} 的密码。", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/reset_password.html", form=form, user=user)


@bp.route("/users/<int:user_id>/id-photo")
@admin_required
def user_id_photo(user_id):
    user = db.get_or_404(User, user_id)
    if not user.student_id_photo:
        abort(404)
    target = Path(current_app.config["ID_PHOTO_FOLDER"]) / user.student_id_photo
    if not target.is_file():
        abort(404)
    return send_file(target, max_age=0)


@bp.route("/users/<int:user_id>/revoke", methods=["POST"])
@admin_required
def revoke_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_admin:
        abort(400)
    user.verification_status = "revoked"
    db.session.commit()
    flash("该用户的校园社区权限已撤销。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@admin_required
def toggle_user_active(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_admin:
        abort(400)
    user.is_active = not user.is_active
    db.session.commit()
    flash("用户账号状态已更新。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/set-admin", methods=["POST"])
@admin_required
def set_admin(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("不能对自己执行此操作。", "danger")
    else:
        user.role = "admin"
        user.verification_status = "verified"
        user.is_active = True
        db.session.commit()
        flash("该用户已成为管理员，可访问管理后台。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/unset-admin", methods=["POST"])
@admin_required
def unset_admin(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("不能移除自己的管理员权限，以免锁定管理后台。", "danger")
    else:
        user.role = "student"
        db.session.commit()
        flash("该用户的管理员权限已移除。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/invites/<int:invite_id>/delete", methods=["POST"])
@admin_required
def delete_invite(invite_id):
    invite = db.get_or_404(InviteCode, invite_id)
    if invite.used_count or invite.redemptions.count():
        flash("已有使用记录的邀请码不能删除，请将其停用。", "danger")
    else:
        db.session.delete(invite)
        db.session.commit()
        flash("未使用的邀请码已删除。", "success")
    return redirect(url_for("admin.invites"))


@bp.route("/posts")
@admin_required
def posts():
    return render_template("admin/posts.html", posts=Post.query.order_by(Post.created_at.desc()).all())


@bp.route("/posts/<int:post_id>/<action>", methods=["POST"])
@admin_required
def moderate_post(post_id, action):
    post = db.get_or_404(Post, post_id)
    if action not in {"approve", "hide", "delete"}:
        abort(404)
    if action == "delete":
        db.session.delete(post)
    else:
        post.status = "approved" if action == "approve" else "hidden"
    db.session.commit()
    flash("帖子状态已更新。", "success")
    return redirect(url_for("admin.posts"))


@bp.route("/comments")
@admin_required
def comments():
    return render_template("admin/comments.html", comments=Comment.query.order_by(Comment.created_at.desc()).all())


@bp.route("/comments/<int:comment_id>/hide", methods=["POST"])
@admin_required
def hide_comment(comment_id):
    comment = db.get_or_404(Comment, comment_id)
    comment.status = "hidden"
    db.session.commit()
    flash("评论已隐藏。", "success")
    return redirect(url_for("admin.comments"))


@bp.route("/reports")
@admin_required
def reports():
    return render_template("admin/reports.html", reports=Report.query.order_by(Report.created_at.desc()).all())


@bp.route("/reports/<int:report_id>/resolve", methods=["POST"])
@admin_required
def resolve_report(report_id):
    report = db.get_or_404(Report, report_id)
    report.status = "resolved"
    db.session.commit()
    flash("举报已标记为已处理。", "success")
    return redirect(url_for("admin.reports"))


@bp.route("/tutors")
@admin_required
def tutors():
    return render_template("admin/tutors.html", profiles=TutorProfile.query.order_by(TutorProfile.created_at.desc()).all())


@bp.route("/tutors/<int:profile_id>/<action>", methods=["POST"])
@admin_required
def moderate_tutor(profile_id, action):
    profile = db.get_or_404(TutorProfile, profile_id)
    if action not in {"approve", "reject"}:
        abort(404)
    profile.status = "approved" if action == "approve" else "rejected"
    db.session.commit()
    flash("家教资料状态已更新。", "success")
    return redirect(url_for("admin.tutors"))


@bp.route("/tutor-requests")
@admin_required
def tutor_requests():
    records = TutorRequest.query.order_by(TutorRequest.created_at.desc()).all()
    return render_template("admin/tutor_requests.html", requests=records)


@bp.route("/tutor-requests/<int:request_id>")
@admin_required
def tutor_request_detail(request_id):
    record = db.get_or_404(TutorRequest, request_id)
    return render_template("admin/tutor_request_detail.html", item=record)


@bp.route("/tutor-requests/<int:request_id>/match", methods=["POST"])
@admin_required
def match_tutor_request(request_id):
    record = db.get_or_404(TutorRequest, request_id)
    record.status = "matched"
    db.session.commit()
    flash("需求已标记为已匹配。", "success")
    return redirect(url_for("admin.tutor_requests"))


@bp.route("/content", methods=["GET", "POST"])
@admin_required
def content():
    if request.method == "POST":
        kind = request.form.get("kind")
        title = request.form.get("title", "").strip()
        body = request.form.get("content", "").strip()
        category = request.form.get("category", "").strip()
        if not title or not body or contains_html(title) or contains_html(body):
            flash("标题和内容不能为空，也不能包含 HTML。", "danger")
        elif kind == "guide" and category in GUIDE_CATEGORIES:
            base_slug = request.form.get("slug", "").strip() or f"guide-{Guide.query.count() + 1}"
            if Guide.query.filter_by(slug=base_slug).first():
                flash("文章别名已存在。", "danger")
                return redirect(url_for("admin.content"))
            db.session.add(Guide(title=title, slug=base_slug, summary=request.form.get("summary", title)[:240], content=body, category=category))
            db.session.commit()
            flash("攻略已创建。", "success")
        elif kind == "english" and category in ENGLISH_CATEGORIES:
            major_code = request.form.get("major", "general")
            if major_code not in RESOURCE_MAJOR_CODES:
                flash("请选择有效的适用专业。", "danger")
            else:
                resource = EnglishResource(title=title, content=body, category=category,
                                           difficulty=request.form.get("difficulty", "入门"))
                resource.set_major(major_code)
                db.session.add(resource)
                db.session.commit()
                flash("英语资料已创建。", "success")
        else:
            flash("内容类型或分类无效。", "danger")
        return redirect(url_for("admin.content"))
    return render_template("admin/content.html", guides=Guide.query.all(), resources=EnglishResource.query.all(),
                           guide_categories=GUIDE_CATEGORIES, english_categories=ENGLISH_CATEGORIES)


@bp.route("/content/<kind>/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_content(kind, item_id):
    model = Guide if kind == "guide" else EnglishResource if kind == "english" else None
    if model is None:
        abort(404)
    db.session.delete(db.get_or_404(model, item_id))
    db.session.commit()
    flash("内容已删除。", "success")
    return redirect(url_for("admin.content"))


@bp.route("/content/<kind>/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_content(kind, item_id):
    model = Guide if kind == "guide" else EnglishResource if kind == "english" else None
    if model is None:
        abort(404)
    item = db.get_or_404(model, item_id)
    categories = GUIDE_CATEGORIES if kind == "guide" else ENGLISH_CATEGORIES
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("content", "").strip()
        category = request.form.get("category", "").strip()
        if not title or not body or category not in categories or contains_html(title) or contains_html(body):
            flash("请完整填写有效内容，且不要包含 HTML。", "danger")
        else:
            item.title = title
            item.content = body
            item.category = category
            if kind == "guide":
                item.summary = request.form.get("summary", "").strip()[:240] or title
            else:
                major_code = request.form.get("major", "general")
                if major_code not in RESOURCE_MAJOR_CODES:
                    flash("请选择有效的适用专业。", "danger")
                    return render_template("admin/edit_content.html", item=item, kind=kind,
                                           categories=categories), 400
                item.set_major(normalize_resource_major(major_code))
                item.difficulty = request.form.get("difficulty", "入门")
            db.session.commit()
            flash("内容已更新。", "success")
            return redirect(url_for("admin.content"))
    return render_template("admin/edit_content.html", item=item, kind=kind, categories=categories)


@bp.route("/content/<kind>/<int:item_id>/publish", methods=["POST"])
@admin_required
def publish_content(kind, item_id):
    model = Guide if kind == "guide" else EnglishResource if kind == "english" else None
    if model is None:
        abort(404)
    item = db.get_or_404(model, item_id)
    item.status = "published"
    db.session.commit()
    flash("内容已审核发布。", "success")
    return redirect(url_for("admin.content"))


@bp.route("/locations", methods=["GET", "POST"])
@admin_required
def locations():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        if not name or not description or category not in LOCATION_CATEGORIES or contains_html(name) or contains_html(description):
            flash("请完整填写有效的地点信息。", "danger")
        else:
            image_path = None
            upload = request.files.get("image")
            if upload and upload.filename:
                try:
                    image_path = save_image(upload)
                except ValueError as error:
                    flash(str(error), "danger")
                    return redirect(url_for("admin.locations"))
            db.session.add(CampusLocation(name=name, description=description, category=category, image_path=image_path))
            db.session.commit()
            flash("地图地点已添加。", "success")
        return redirect(url_for("admin.locations"))
    return render_template("admin/locations.html", locations=CampusLocation.query.all(), categories=LOCATION_CATEGORIES)


@bp.route("/locations/<int:location_id>/delete", methods=["POST"])
@admin_required
def delete_location(location_id):
    db.session.delete(db.get_or_404(CampusLocation, location_id))
    db.session.commit()
    flash("地图地点已删除。", "success")
    return redirect(url_for("admin.locations"))


@bp.route("/locations/<int:location_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_location(location_id):
    item = db.get_or_404(CampusLocation, location_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        if not name or not description or category not in LOCATION_CATEGORIES or contains_html(name) or contains_html(description):
            flash("请完整填写有效的地点信息。", "danger")
        else:
            item.name, item.description, item.category = name, description, category
            upload = request.files.get("image")
            if upload and upload.filename:
                try:
                    item.image_path = save_image(upload)
                except ValueError as error:
                    flash(str(error), "danger")
                    return redirect(url_for("admin.edit_location", location_id=item.id))
            db.session.commit()
            flash("地图地点已更新。", "success")
            return redirect(url_for("admin.locations"))
    return render_template("admin/edit_location.html", item=item, categories=LOCATION_CATEGORIES)
